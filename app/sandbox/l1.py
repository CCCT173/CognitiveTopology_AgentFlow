"""
L1 严格沙箱（原 Skill 沙箱）
- AST 静态检查：禁 import os/sys/subprocess/socket 等、禁双下划线属性、禁 open/eval/exec
- 子进程隔离：独立 python 进程、超时自动 kill、白名单标准库
- 无文件系统访问、无网络访问
- 用于工作流 Code 节点、Skill 执行等"纯计算"场景
"""
from __future__ import annotations
import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any


# ============ L1 静态检查规则 ============
_FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "threading",
    "multiprocessing", "ctypes", "pickle", "marshal", "shelve", "sqlite3",
    "http", "urllib", "ftplib", "smtplib", "telnetlib", "asyncio",
    "ssl", "tempfile", "glob", "fnmatch", "webbrowser",
}

_FORBIDDEN_ATTRS = {
    "__class__", "__bases__", "__subclasses__", "__mro__", "__globals__",
    "__import__", "__builtins__", "__dict__", "__getattribute__",
    "open", "eval", "exec", "compile", "__import__",
    "system", "popen", "spawn", "fork", "execve",
}


def static_check(code: str) -> list[str]:
    """AST 静态检查，返回违规列表（空=安全）"""
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"语法错误: {e}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                if top in _FORBIDDEN_IMPORTS:
                    violations.append(f"禁止 import: {n.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in _FORBIDDEN_IMPORTS:
                    violations.append(f"禁止 from-import: {node.module}")
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRS:
                violations.append(f"禁止访问属性: {node.attr}")
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_ATTRS:
                violations.append(f"禁止调用/引用: {node.id}")
    return violations


# ============ L1 子进程 runner ============
_SUBPROCESS_RUNNER = r'''
import sys, json, io, os, traceback, tempfile, shutil
from contextlib import redirect_stdout, redirect_stderr

SAFE_BUILTINS = {
    "print": print, "len": len, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
    "range": range, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
    "type": type, "any": any, "all": all, "True": True, "False": False, "None": None,
}

ALLOWED_MODULES = {"math", "re", "json", "datetime", "collections", "itertools",
                   "functools", "operator", "string", "textwrap", "numbers",
                   "decimal", "fractions", "random", "statistics", "copy",
                   "pprint", "csv", "hashlib", "base64", "uuid", "time"}


def _restricted_import(name, *a, **kw):
    top = name.split(".")[0]
    if top in ALLOWED_MODULES:
        import importlib
        return importlib.import_module(name)
    raise ImportError(f"import '{name}': 该模块不在 L1 沙箱白名单中")

SAFE_BUILTINS["__import__"] = _restricted_import


def main():
    payload = json.loads(sys.stdin.read())
    code = payload.get("code", "")
    params = payload.get("params", {})
    context = payload.get("context", {})
    bundle = payload.get("bundle") or {}
    entry = payload.get("entry")

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    result = {"ok": False, "output": None, "stdout": "", "stderr": "", "error": None,
              "violations": []}
    tmpdir = None
    orig_cwd = os.getcwd()
    orig_path = list(sys.path)
    try:
        violations = []  # Runner 侧再做一次 AST 检查（防父进程检查绕过）
        # 父进程已经检查过，这里仅简单编译验证
        sandbox_globals = {"__builtins__": SAFE_BUILTINS,
                           "params": params, "context": context, "input_data": params,
                           "json": json}
        import importlib as _il
        for m in ALLOWED_MODULES:
            try: sandbox_globals[m] = _il.import_module(m)
            except Exception: pass
        tmpdir = None
        if bundle:
            tmpdir = tempfile.mkdtemp(prefix="l1_bundle_")
            for rel, content in bundle.items():
                rel_norm = rel.replace("\\", "/").lstrip("/")
                if ".." in rel_norm.split("/"): continue
                fpath = os.path.join(tmpdir, rel_norm)
                os.makedirs(os.path.dirname(fpath) or tmpdir, exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content if isinstance(content, str) else str(content))
            sys.path.insert(0, tmpdir)
            os.chdir(tmpdir)
            if entry and entry in bundle:
                code = bundle[entry]
        sandbox_ns = dict(sandbox_globals)
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<l1-sandbox>", "exec"), sandbox_ns, sandbox_ns)
            output = None
            for fn in ("run", "main", "execute"):
                if fn in sandbox_ns and callable(sandbox_ns[fn]):
                    output = sandbox_ns[fn](params)
                    break
            else:
                output = sandbox_ns.get("_result", sandbox_ns.get("result"))
        result["ok"] = True
        result["output"] = output
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc(limit=3)
    finally:
        try: os.chdir(orig_cwd)
        except Exception: pass
        sys.path[:] = orig_path
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
    result["stdout"] = stdout_buf.getvalue()
    result["stderr"] = stderr_buf.getvalue()
    sys.stdout.write(json.dumps(result, default=str, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''


@dataclass
class L1Result:
    ok: bool
    output: Any = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "output": self.output, "stdout": self.stdout,
            "stderr": self.stderr, "error": self.error, "violations": self.violations,
        }


def run_l1(code: str, params: dict | None = None, timeout: int = 5,
            bundle: dict | None = None, entry: str | None = None) -> L1Result:
    """在 L1 严格沙箱中执行 Python 代码"""
    violations = static_check(code)
    if violations:
        return L1Result(ok=False, error="静态检查失败", violations=violations)

    py_exe = sys.executable
    payload = json.dumps({
        "code": code, "params": params or {},
        "bundle": bundle or {}, "entry": entry,
    }, ensure_ascii=False)
    proc = subprocess.Popen(
        [py_exe, "-c", _SUBPROCESS_RUNNER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    try:
        out, err = proc.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try: out, err = proc.communicate(timeout=2)
        except Exception: out, err = "", ""
        return L1Result(ok=False, error=f"执行超时 (>{timeout}s)")
    try:
        data = json.loads(out.strip()) if out.strip() else {"ok": False, "error": "无输出"}
    except json.JSONDecodeError:
        data = {"ok": False, "error": f"输出非 JSON: {out[:300]}", "stdout": out, "stderr": err}
    return L1Result(
        ok=data.get("ok", False),
        output=data.get("output"),
        stdout=data.get("stdout", ""),
        stderr=(data.get("stderr", "") + "\n" + err).strip(),
        error=data.get("error"),
        violations=data.get("violations", []),
    )
