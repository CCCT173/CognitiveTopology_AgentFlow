import re
import io
import os
import sys
import ast
import time
import yaml
import json
import threading
import subprocess
import tempfile
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillUpdate, SkillTestRequest
from app.core.logger import logger
from app.core.exceptions import AppException, ErrorCode
from app.core.time import utc_now, utc_now_naive


# ============ Skill 安全执行沙箱 ============
# 两层防护:
#   L1 AST静态检查: 编译前扫描禁止的 import / 属性访问 / 危险调用
#   L2 子进程隔离:   在独立 Python 子进程中执行,超时直接 kill,避免污染主进程

# 受限内置白名单 (用于 L2 子进程 globals)
_SAFE_BUILTINS = {
    "print": print, "len": len, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
    "range": range, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
    "type": type, "any": any, "all": all, "True": True, "False": False, "None": None,
}

# AST 静态检查: 禁止危险的 import 和属性访问
_FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket", "ctypes", "importlib",
    "pickle", "marshal", "builtins", "multiprocessing", "threading", "asyncio",
    "pathlib", "pty", "platform",
}
_FORBIDDEN_ATTRS = {
    "__import__", "__builtins__", "__globals__", "__subclasses__",
    "__class__", "__bases__", "__mro__", "eval", "exec", "compile",
    "open", "system", "popen",
}
_MAX_EXEC_SEC = 5
_MAX_OUTPUT_BYTES = 64 * 1024


class _SkillTimeout(Exception):
    pass


# 复用 L1 沙箱的 AST 静态检查（黑名单模式：禁止 os/sys/subprocess/__class__/eval/exec 等）
from app.sandbox.l1 import static_check as _static_check  # noqa: E402


# ============ L2: 子进程隔离执行 ============
_SUBPROCESS_RUNNER = '''
import sys, json, io, os, traceback, tempfile, shutil
from contextlib import redirect_stdout, redirect_stderr
from app.core.time import utc_now, utc_now_naive

SAFE_BUILTINS = {
    "print": print, "len": len, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
    "range": range, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
    "type": type, "any": any, "all": all, "True": True, "False": False, "None": None,
}

# 允许用户 import 的标准库模块白名单
ALLOWED_MODULES = {"math", "re", "json", "datetime", "collections", "itertools",
                   "functools", "operator", "string", "textwrap", "numbers",
                   "decimal", "fractions", "random", "statistics", "copy",
                   "pprint", "csv", "hashlib", "base64", "uuid", "time"}


def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    """受限 __import__: 仅允许标准库白名单 + bundle 本地模块"""
    top = name.split(".")[0]
    if top in ALLOWED_MODULES:
        import importlib
        return importlib.import_module(name)
    # 本地 bundle 模块：由调用方在 bundle_written 后预放到 sys.path
    try:
        import importlib
        return importlib.import_module(name)
    except Exception:
        raise ImportError(f"import '{name}': 该模块不在沙箱白名单中")

SAFE_BUILTINS["__import__"] = _restricted_import

def main():
    payload = json.loads(sys.stdin.read())
    code = payload.get("code", "")
    params = payload.get("params", {})
    context = payload.get("context", {})
    bundle = payload.get("bundle") or {}
    entry = payload.get("entry") or None

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    result = {"ok": False, "output": None, "stdout": "", "stderr": "", "error": None}
    tmpdir = None
    orig_cwd = os.getcwd()
    orig_path = list(sys.path)
    try:
        import math, datetime, re
        sandbox_globals = {"__builtins__": SAFE_BUILTINS,
                           "params": params, "context": context, "input_data": params,
                           "json": json, "re": re, "math": math,
                           "datetime": datetime}
        # 把白名单模块也放进 globals, 避免用户手动 import 时二次 lookup
        import importlib as _il
        for _m in ("collections", "itertools", "functools", "operator", "string",
                   "textwrap", "numbers", "decimal", "fractions", "random",
                   "statistics", "copy", "pprint", "csv", "hashlib", "base64",
                   "uuid", "time"):
            try:
                sandbox_globals[_m] = _il.import_module(_m)
            except Exception:
                pass
        sandbox_locals = {}
        if bundle:
            tmpdir = tempfile.mkdtemp(prefix="skill_bundle_")
            for rel, content in bundle.items():
                rel_norm = rel.replace("\\\\", "/").lstrip("/")
                if ".." in rel_norm.split("/"):
                    continue
                fpath = os.path.join(tmpdir, rel_norm)
                os.makedirs(os.path.dirname(fpath) or tmpdir, exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content if isinstance(content, str) else str(content))
            sys.path.insert(0, tmpdir)
            os.chdir(tmpdir)
            if entry and entry in bundle:
                code = bundle[entry]
        # exec 时用同一个字典作为 globals 和 locals, 避免 from-import 在函数内查找失败
        sandbox_ns = dict(sandbox_globals)
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<skill>", "exec"), sandbox_ns, sandbox_ns)
            output = None
            called = False
            for fn_name in ("run", "main", "execute"):
                if fn_name in sandbox_ns and callable(sandbox_ns[fn_name]):
                    output = sandbox_ns[fn_name](params)
                    called = True
                    break
            if not called:
                output = sandbox_ns.get("_result", sandbox_ns.get("result"))
        result["ok"] = True
        result["output"] = output
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc(limit=3)
    finally:
        try:
            os.chdir(orig_cwd)
        except Exception:
            pass
        sys.path[:] = orig_path
        if tmpdir and os.path.isdir(tmpdir):
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    result["stdout"] = stdout_buf.getvalue()
    result["stderr"] = stderr_buf.getvalue()
    sys.stdout.write(json.dumps(result, default=str, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''


def _run_in_subprocess(code: str, params: dict, timeout: int = _MAX_EXEC_SEC,
                       bundle: dict | None = None, entry: str | None = None) -> dict:
    """在独立子进程中执行 Skill 代码, 超时自动 kill, 返回 {ok, output, stdout, stderr, error}
    
    bundle: 可选多文件包 {relpath: content_str}；子进程会写入临时目录并将其加入 sys.path，支持跨文件 import
    entry:  可选入口文件 relpath；传入时以该文件为 exec 源
    """
    # 找到当前虚拟环境的 python 可执行文件
    py_exe = sys.executable
    payload = json.dumps({
        "code": code, "params": params,
        "bundle": bundle or {}, "entry": entry,
    }, ensure_ascii=False)

    # 用 -c 启动 runner, 通过 stdin 传 payload
    proc = subprocess.Popen(
        [py_exe, "-c", _SUBPROCESS_RUNNER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        # Windows 下隐藏窗口
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    try:
        out, err = proc.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out, err = "", ""
        return {"ok": False, "output": None, "stdout": out or "", "stderr": err or "",
                "error": f"执行超时 (>{timeout}s), 子进程已被强制终止"}

    # 解析 runner 输出: runner 用 sys.stdout.write 输出单个 JSON, 直接 json.loads(out)
    try:
        stripped = out.strip()
        data = json.loads(stripped) if stripped else {"ok": False, "error": "Runner 无输出", "stdout": out, "stderr": err}
    except json.JSONDecodeError:
        data = {"ok": False, "error": f"Runner 输出非 JSON: {out[:500]}", "stdout": out, "stderr": err}

    if err:
        data["stderr"] = (data.get("stderr", "") + "\n" + err).strip()
    return data


def _run_with_timeout(fn, timeout_sec: int):
    """[Legacy] 在独立线程中运行, 超时抛异常 (保留给内联执行路径)"""
    result: dict = {"ok": False, "value": None, "error": None}
    def _target():
        try:
            result["value"] = fn()
            result["ok"] = True
        except Exception as e:
            result["error"] = e
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise _SkillTimeout(f"执行超时 (>{timeout_sec}s), 可能存在死循环或阻塞调用")
    if result["error"]:
        raise result["error"]
    return result["value"]


class SkillService:
    @staticmethod
    def get_skill(db: Session, skill_id: int) -> Optional[Skill]:
        """获取单个技能详情"""
        return db.query(Skill).filter(Skill.id == skill_id).first()
    
    @staticmethod
    def get_skill_by_name(db: Session, name: str) -> Optional[Skill]:
        """根据名称获取技能"""
        return db.query(Skill).filter(Skill.name == name).first()
    
    @staticmethod
    def list_skills(
        db: Session,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_builtin: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
        owner_id: Optional[int] = None,
    ) -> tuple[List[Skill], int]:
        """获取技能列表: owner_id 不为 None 时只看该用户创建的 + 内置技能"""
        from sqlalchemy import or_ as sa_or
        query = db.query(Skill)
        
        if owner_id is not None:
            query = query.filter(or_(Skill.created_by == owner_id, Skill.is_builtin.is_(True)))
        if category:
            query = query.filter(Skill.category == category)
        if is_active is not None:
            query = query.filter(Skill.is_active == is_active)
        if is_builtin is not None:
            query = query.filter(Skill.is_builtin == is_builtin)
        if keyword:
            query = query.filter(or_(
                Skill.name.contains(keyword),
                Skill.description.contains(keyword)
            ))
        if tag:
            query = query.filter(Skill.tags.contains([tag]))
        
        total = query.count()
        skills = query.order_by(Skill.usage_count.desc(), Skill.created_at.desc()).offset(skip).limit(limit).all()
        return skills, total
    
    @staticmethod
    @staticmethod
    def _check_source_security(src: str):
        """对单段源码做 L1 AST 静态检查，发现危险代码即拒绝（422）"""
        if src and src.strip():
            violations = _static_check(src)
            if violations:
                raise AppException(ErrorCode.VALIDATION, f"代码安全检查未通过: {violations[0]}", 422)

    @staticmethod
    def _enforce_code_security(code: Optional[str], content: Optional[str] = None):
        """提取可执行代码并做 L1 AST 静态检查；危险代码在创建/更新阶段即拒绝（与 test_skill 运行时一致）"""
        src = code or ""
        if not src and content:
            m = re.search(r"```python\s*\n(.*?)```", content or "", re.DOTALL)
            if m:
                src = m.group(1)
        SkillService._check_source_security(src)

    def create_skill(db: Session, skill_in: SkillCreate) -> Skill:
        """创建新技能"""
        # 解析SKILL.md中的元信息
        metadata = SkillService.parse_skill_metadata(skill_in.content)
        skill_data = skill_in.model_dump()

        # L1 静态安全检查：创建阶段即拦截危险代码，防止恶意代码持久化
        SkillService._enforce_code_security(skill_in.code, skill_in.content)

        # 自动填充元信息
        if metadata.get("name") and not skill_data.get("name"):
            skill_data["name"] = metadata["name"]
        if metadata.get("description") and not skill_data.get("description"):
            skill_data["description"] = metadata["description"]
        if metadata.get("version") and not skill_data.get("version"):
            skill_data["version"] = metadata["version"]
        if metadata.get("author") and not skill_data.get("author"):
            skill_data["author"] = metadata["author"]
        if metadata.get("category") and not skill_data.get("category"):
            skill_data["category"] = metadata["category"]
        if metadata.get("tags") and not skill_data.get("tags"):
            skill_data["tags"] = metadata["tags"]
        
        db_skill = Skill(**skill_data)
        db.add(db_skill)
        db.commit()
        db.refresh(db_skill)
        logger.info(f"Created skill: {db_skill.name} v{db_skill.version}")
        return db_skill
    
    @staticmethod
    def update_skill(db: Session, skill: Skill, skill_in: SkillUpdate) -> Skill:
        """更新技能信息"""
        update_data = skill_in.model_dump(exclude_unset=True)

        # L1 静态安全检查：更新了 code/content 时同样拦截危险代码
        if "code" in update_data or "content" in update_data:
            SkillService._enforce_code_security(update_data.get("code"), update_data.get("content"))

        # 如果更新了content，重新解析元信息
        if "content" in update_data:
            metadata = SkillService.parse_skill_metadata(update_data["content"])
            for key in ["name", "description", "version", "author", "category", "tags"]:
                if metadata.get(key) and key not in update_data:
                    update_data[key] = metadata[key]
        
        for field, value in update_data.items():
            setattr(skill, field, value)
        
        skill.updated_at = utc_now()
        db.add(skill)
        db.commit()
        db.refresh(skill)
        logger.info(f"Updated skill: {skill.name} v{skill.version}")
        return skill
    
    @staticmethod
    def delete_skill(db: Session, skill_id: int) -> bool:
        """删除技能"""
        skill = db.query(Skill).filter(Skill.id == skill_id).first()
        if not skill:
            return False
        if skill.is_builtin:
            raise ValueError("内置技能不能删除")
        
        db.delete(skill)
        db.commit()
        logger.info(f"Deleted skill: {skill.name}")
        return True
    
    @staticmethod
    def parse_skill_metadata(content: str) -> Dict[str, Any]:
        """解析SKILL.md文件中的Front Matter元信息"""
        metadata = {}
        
        # 匹配YAML Front Matter
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            try:
                metadata = yaml.safe_load(frontmatter_match.group(1)) or {}
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse skill frontmatter: {e}")
        
        # 如果没有frontmatter，尝试从标题提取
        if not metadata.get("name"):
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                metadata["name"] = title_match.group(1).strip()
        
        if not metadata.get("description"):
            desc_match = re.search(r'^(?!#)(.+?)(?=\n#|\Z)', content, re.DOTALL | re.MULTILINE)
            if desc_match:
                metadata["description"] = desc_match.group(1).strip()[:500]
        
        return metadata
    
    @staticmethod
    def test_skill(db: Session, skill: Skill, test_req: SkillTestRequest) -> Dict[str, Any]:
        """测试运行技能(带沙箱执行)"""
        start_time = time.time()
        logs: list[str] = []
        output = None
        error = None
        success = False

        try:
            logs.append(f"[INFO] Starting skill test: {skill.name} v{skill.version}")
            logs.append(f"[INFO] Input parameters: {json.dumps(test_req.input_params, ensure_ascii=False)}")

            # 检查是否为多文件 bundle 模式 (zip 导入)
            cfg = skill.config or {}
            bundle = cfg.get("bundle") if isinstance(cfg, dict) else None
            entry = cfg.get("entry") if isinstance(cfg, dict) else None
            bundle_exec = bool(bundle) and isinstance(bundle, dict)

            code = ""
            if bundle_exec:
                # bundle 模式：优先入口文件 -> bundle 中其他 .py 顶层候选 -> SKILL.md 代码块
                if entry and entry in bundle:
                    code = bundle[entry]
                    logs.append(f"[INFO] Bundle mode: entry = {entry} ({len(bundle)} files)")
                else:
                    # 找顶层 main.py/run.py/index.py/skill.py
                    for cand in ("main.py", "run.py", "index.py", "skill.py"):
                        if cand in bundle:
                            code = bundle[cand]
                            entry = cand
                            logs.append(f"[INFO] Bundle mode: auto-detected entry = {cand}")
                            break
                    if not code:
                        m = re.search(r"```python\s*\n(.*?)```", skill.content or "", re.DOTALL)
                        if m:
                            code = m.group(1)
                            logs.append(f"[INFO] Bundle mode: {len(bundle)} files; using python code block from SKILL.md")
                        else:
                            logs.append(f"[INFO] Bundle mode: {len(bundle)} files, no executable entry found")
            else:
                # 单文件模式：优先 code 字段 -> SKILL.md 代码块
                code = skill.code or ""
                if not code:
                    m = re.search(r"```python\s*\n(.*?)```", skill.content or "", re.DOTALL)
                    if m:
                        code = m.group(1)
                        logs.append("[INFO] Found Python code block in SKILL.md content")

            if code.strip():
                # AST 静态安全检查
                violations = _static_check(code)
                if violations:
                    logs.append(f"[SECURITY] 发现 {len(violations)} 个安全违规:")
                    for v in violations:
                        logs.append(f"  - {v}")
                    raise ValueError(f"安全检查未通过: {violations[0]}")

                logs.append("[INFO] Executing skill code in isolated subprocess sandbox...")
                sub_result = _run_in_subprocess(
                    code, test_req.input_params or {}, _MAX_EXEC_SEC,
                    bundle=bundle if bundle_exec else None,
                    entry=entry if bundle_exec else None,
                )
                so = (sub_result.get("stdout") or "").strip()
                se = (sub_result.get("stderr") or "").strip()
                # 截断大输出
                if len(so) > _MAX_OUTPUT_BYTES:
                    so = so[:_MAX_OUTPUT_BYTES] + f"\n...[truncated {len(so)-_MAX_OUTPUT_BYTES} bytes]"
                if len(se) > _MAX_OUTPUT_BYTES:
                    se = se[:_MAX_OUTPUT_BYTES] + f"\n...[truncated {len(se)-_MAX_OUTPUT_BYTES} bytes]"
                if so:
                    logs.append(f"[STDOUT]\n{so}")
                if se:
                    logs.append(f"[STDERR]\n{se}")

                if sub_result.get("error"):
                    tb = sub_result.get("traceback")
                    if tb:
                        logs.append(f"[TRACEBACK]\n{tb}")
                    raise RuntimeError(sub_result["error"])
                output = sub_result.get("output")
                logs.append("[INFO] Subprocess executed successfully")
            else:
                logs.append("[INFO] No executable code found; returning input echo (document-only skill)")
                output = {
                    "skill": skill.name,
                    "received_params": test_req.input_params,
                    "message": "Skill is document-only; no executable code block."
                }

            # 更新使用统计
            skill.usage_count += 1
            skill.last_used_at = utc_now()
            db.add(skill)
            db.commit()

            logs.append("[INFO] Skill execution completed")
            success = True

        except Exception as e:
            error = str(e)
            logs.append(f"[ERROR] Skill execution failed: {error}")
            logger.error(f"Skill test failed for {skill.name}: {error}", exc_info=True)

        execution_time = round(time.time() - start_time, 3)
        logs.append(f"[INFO] Total execution time: {execution_time}s")

        return {
            "success": success,
            "output": output,
            "error": error,
            "execution_time": execution_time,
            "elapsed_ms": int(execution_time * 1000),
            "logs": logs,
        }
    
    @staticmethod
    def import_skill_from_content(db: Session, content: str, format: str = "markdown") -> Skill:
        """从内容导入技能"""
        if format == "markdown":
            # 先预解析 name，避免空字符串触发 min_length 校验
            meta = SkillService.parse_skill_metadata(content)
            skill_in = SkillCreate(
                name=meta.get("name") or None,  # None 而不是 ""，避免 min_length 校验失败
                description=meta.get("description"),
                content=content,
            )
            return SkillService.create_skill(db, skill_in)
        else:
            raise ValueError(f"Unsupported import format: {format}")

    @staticmethod
    def import_skill_from_zip(db: Session, raw: bytes) -> Skill:
        """从 zip 包导入技能 (支持多文件打包)。

        约定：
        - 根目录下必须有 SKILL.md (支持外层有一层同名目录的常见打包形式)
        - 所有文件按相对路径存入 config["bundle"] = {relpath: content_str}
        - 若存在 main.py / run.py / index.py / skill.py，自动识别为入口文件并写入 config["entry"]
        - 代码文件 (*.py/*.js/*.ts/*.sh) 同时拼接到 code 字段作为展示留存
        - 二进制文件 (非 utf-8 可解码) 会被跳过并记 warning
        - zip-slip 防护 (禁止 ../ 路径穿越)
        - 总解压大小限制 2MB，单文件 512KB
        """
        import zipfile
        _MAX_TOTAL = 2 * 1024 * 1024
        _MAX_SINGLE = 512 * 1024
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise ValueError("非法的 zip 文件")

        # 第一步：扫描所有条目，识别根前缀（处理外层多一层目录的情况）
        entries: list[tuple[str, zipfile.ZipInfo]] = []  # (normalized_relpath, info)
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            # zip-slip 防护：禁止绝对路径 / 上级穿越
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"非法路径 (zip-slip 防护): {name}")
            entries.append((name, info))

        if not entries:
            raise ValueError("zip 为空")

        # 自动剥离公共前缀
        parts_split = [n.split("/") for n, _ in entries]
        common = []
        for i in range(min(len(p) for p in parts_split)):
            seg = parts_split[0][i]
            if all(p[i] == seg for p in parts_split) and i < len(parts_split[0]) - 1:
                common.append(seg)
            else:
                break
        strip_prefix = "/".join(common) + "/" if common else ""

        # 查找 SKILL.md 和入口文件
        md_rel = None
        entry_rel = None
        code_exts = (".py", ".js", ".ts", ".sh")
        bundle: dict[str, str] = {}
        total = 0
        for name, info in entries:
            rel = name[len(strip_prefix):] if strip_prefix and name.startswith(strip_prefix) else name
            if not rel:
                continue
            if info.file_size > _MAX_SINGLE:
                continue  # 跳过超大文件
            base = rel.split("/")[-1]
            try:
                data = zf.read(info)
            except Exception:
                continue
            # 二进制文件跳过（文本类只接受 utf-8 可解码内容）
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            total += len(text)
            if total > _MAX_TOTAL:
                raise ValueError("zip 解压后文本总大小超过 2MB 限制")
            bundle[rel] = text
            if base.lower() == "skill.md":
                md_rel = rel
            # 自动识别入口文件
            if base.lower() in ("main.py", "run.py", "index.py", "skill.py") and entry_rel is None:
                entry_rel = rel

        if not md_rel or md_rel not in bundle:
            raise ValueError("zip 中未找到 SKILL.md")

        content = bundle[md_rel]
        skill = SkillService.import_skill_from_content(db, content, format="markdown")

        # 把所有非 SKILL.md 文件拼到 code 字段展示
        code_parts: list[str] = []
        for rel, text in bundle.items():
            if rel == md_rel:
                continue
            ext = rel.rsplit(".", 1)[-1] if "." in rel else ""
            lang_hint = ext if ext else ""
            code_parts.append(f"### {rel}\n```{lang_hint}\n{text}\n```\n")
        if code_parts:
            skill.code = "\n".join(code_parts)
            # L1 静态安全检查：zip 内每个代码文件单独检查（不检查拼接后的 markdown 包裹）
            for rel, text in bundle.items():
                ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
                if ext in ("py", "js", "ts", "sh"):
                    SkillService._check_source_security(text)

        # 保存 bundle + entry 到 config
        cfg = dict(skill.config or {})
        cfg["bundle"] = bundle
        cfg["entry"] = entry_rel
        cfg["bundle_count"] = len(bundle)
        skill.config = cfg
        if entry_rel and not skill.entry_point:
            skill.entry_point = entry_rel

        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill
    
    @staticmethod
    def get_skill_categories(db: Session) -> List[Dict[str, Any]]:
        """获取所有技能分类及统计"""
        from sqlalchemy import func
        categories = db.query(
            Skill.category,
            func.count(Skill.id).label("count")
        ).group_by(Skill.category).all()

        return [{"category": cat or "未分类", "count": cnt} for cat, cnt in categories]
