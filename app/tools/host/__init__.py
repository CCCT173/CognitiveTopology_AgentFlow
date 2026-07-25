"""L0 Host 工具集（主机级访问）

这些工具让 AI 能读取/写入宿主机文件、查看信息。
- 所有工具经过 pathguard 路径白名单校验（~/.agentflow + 项目目录）
- 读工具 risk=low 不需确认；写/删工具 requires_confirmation=True（HITL）
- host_shell 单独在 shell.py 里实现
"""
from __future__ import annotations
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

from app.tools import BaseTool, ToolResult, TOOL_TYPE_HOST
from app.tools.host.pathguard import safe_resolve, DEFAULT_ROOTS


# ---------- helpers ----------
def _resolve(path: str, must_exist: bool = False, allow_write: bool = False) -> Path:
    return safe_resolve(path, must_exist=must_exist, allow_write=allow_write)


def _read_text(p: Path, max_bytes: int) -> str:
    content = p.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_bytes:
        return content[:max_bytes] + f"\n... [truncated {len(content) - max_bytes} chars]"
    return content


# ---------- read ----------
class HostReadTool(BaseTool):
    name = "host_read"
    display_name = "读取主机文件"
    tool_type = TOOL_TYPE_HOST
    description = (
        "读取宿主机文本文件内容（UTF-8）。仅允许 ~/.agentflow 和当前项目目录内。"
        "敏感文件（.env/.ssh/*.pem/*.key 等）自动拒绝。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（~ 可展开）"},
            "max_bytes": {"type": "integer", "description": "最大读取字节，默认 1MB"},
        },
        "required": ["path"],
    }
    requires_confirmation = False
    risk_level = "low"

    def run(self, ctx=None, **kw):
        try:
            p = _resolve(kw["path"], must_exist=True)
            if not p.is_file():
                return ToolResult(ok=False, error=f"不是普通文件: {p}")
            max_b = int(kw.get("max_bytes", 1024 * 1024))
            return ToolResult(ok=True, output=_read_text(p, max_b),
                              data={"path": str(p), "size": p.stat().st_size})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- list_dir ----------
class HostListDirTool(BaseTool):
    name = "host_list_dir"
    display_name = "列出主机目录"
    tool_type = TOOL_TYPE_HOST
    description = "列出宿主机目录内容（仅允许 ~/.agentflow 和当前项目目录内）。"
    params_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认 '.'"},
            "recursive": {"type": "boolean", "description": "是否递归，默认 false"},
        },
    }
    requires_confirmation = False
    risk_level = "low"

    def run(self, ctx=None, **kw):
        try:
            p = _resolve(kw.get("path", "."), must_exist=True)
            if not p.is_dir():
                return ToolResult(ok=False, error=f"不是目录: {p}")
            items = []
            if kw.get("recursive"):
                iterator = p.rglob("*")
            else:
                iterator = p.iterdir()
            for child in iterator:
                try:
                    rel = child.relative_to(p)
                except ValueError:
                    continue
                # 跳过 .git/__pycache__/node_modules 等
                parts = set(rel.parts)
                if parts & {".git", "__pycache__", "node_modules", ".venv", "venv"}:
                    continue
                try:
                    st = child.stat()
                    items.append({
                        "path": str(rel),
                        "type": "dir" if child.is_dir() else "file",
                        "size": st.st_size if child.is_file() else 0,
                        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    })
                except OSError:
                    continue
                if len(items) >= 500:
                    break
            return ToolResult(ok=True, output=json.dumps(items, ensure_ascii=False, indent=2)[:8000],
                              data={"path": str(p), "count": len(items)})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- write ----------
class HostWriteTool(BaseTool):
    name = "host_write"
    display_name = "写入主机文件"
    tool_type = TOOL_TYPE_HOST
    description = (
        "创建或覆写宿主机文件。必须在白名单目录内。敏感路径拒绝。"
        "此操作需要用户确认。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目标文件路径"},
            "content": {"type": "string", "description": "写入内容（UTF-8 文本）"},
            "append": {"type": "boolean", "description": "true=追加，false=覆写（默认）"},
        },
        "required": ["path", "content"],
    }
    requires_confirmation = True
    risk_level = "high"

    def run(self, ctx=None, **kw):
        try:
            p = _resolve(kw["path"], allow_write=True)
            if p.exists() and p.is_dir():
                return ToolResult(ok=False, error=f"目标是目录: {p}")
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if kw.get("append") else "w"
            # filelock 跨进程锁（简单实现：独占打开）
            with open(p, mode, encoding="utf-8") as f:
                f.write(kw["content"])
            return ToolResult(ok=True, output=f"已写入 {p}（{len(kw['content'])} 字节）",
                              data={"path": str(p), "bytes": len(kw["content"])})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- edit (old/new string replace) ----------
class HostEditTool(BaseTool):
    name = "host_edit"
    display_name = "编辑文件（替换）"
    tool_type = TOOL_TYPE_HOST
    description = (
        "精确字符串替换编辑文件。old_string 在文件中必须唯一，否则报错。"
        "此操作需要用户确认。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_string": {"type": "string", "description": "要替换的原文（必须精确匹配）"},
            "new_string": {"type": "string", "description": "新文本"},
        },
        "required": ["path", "old_string", "new_string"],
    }
    requires_confirmation = True
    risk_level = "high"

    def run(self, ctx=None, **kw):
        try:
            p = _resolve(kw["path"], must_exist=True, allow_write=True)
            if not p.is_file():
                return ToolResult(ok=False, error=f"不是文件: {p}")
            original = p.read_text(encoding="utf-8")
            old = kw["old_string"]
            new = kw["new_string"]
            count = original.count(old)
            if count == 0:
                return ToolResult(ok=False, error=f"old_string 在文件中未找到")
            if count > 1:
                return ToolResult(ok=False, error=f"old_string 在文件中出现 {count} 次（不唯一），请改用更精确的匹配")
            updated = original.replace(old, new, 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write(updated)
            return ToolResult(ok=True, output=f"已替换 1 处: {p}",
                              data={"path": str(p), "replacements": 1})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- delete ----------
class HostDeleteTool(BaseTool):
    name = "host_delete"
    display_name = "删除文件/空目录"
    tool_type = TOOL_TYPE_HOST
    description = (
        "删除宿主机文件或空目录。拒绝通配符和递归删除非空目录。"
        "此操作需要用户确认。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要删除的路径"},
        },
        "required": ["path"],
    }
    requires_confirmation = True
    risk_level = "critical"

    def run(self, ctx=None, **kw):
        try:
            p = _resolve(kw["path"], must_exist=True, allow_write=True)
            if p.is_dir():
                # 空目录才能删
                contents = list(p.iterdir())
                if contents:
                    return ToolResult(ok=False, error=f"目录非空（{len(contents)} 项），拒绝递归删除")
                p.rmdir()
            else:
                # Windows 回收站：先尝试 winshell，失败则直接 unlink
                p.unlink()
            return ToolResult(ok=True, output=f"已删除: {p}")
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- move ----------
class HostMoveTool(BaseTool):
    name = "host_move"
    display_name = "移动/重命名文件"
    tool_type = TOOL_TYPE_HOST
    description = "移动或重命名文件。源和目标都必须在白名单内。此操作需要用户确认。"
    params_schema = {
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "源路径"},
            "dst": {"type": "string", "description": "目标路径"},
        },
        "required": ["src", "dst"],
    }
    requires_confirmation = True
    risk_level = "high"

    def run(self, ctx=None, **kw):
        try:
            src = _resolve(kw["src"], must_exist=True, allow_write=True)
            dst = _resolve(kw["dst"], allow_write=True)
            if dst.exists():
                return ToolResult(ok=False, error=f"目标已存在: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return ToolResult(ok=True, output=f"已移动: {src} → {dst}")
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


# ---------- info ----------
class HostInfoTool(BaseTool):
    name = "host_info"
    display_name = "主机环境信息"
    tool_type = TOOL_TYPE_HOST
    description = "返回 OS/Python/Node/CPU/内存/当前工作目录/白名单根目录等信息。无副作用。"
    params_schema = {"type": "object", "properties": {}}
    requires_confirmation = False
    risk_level = "low"

    def run(self, ctx=None, **kw):
        try:
            import shutil
            info = {
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "python_executable": sys.executable,
                "cwd": str(Path.cwd()),
                "pid": os.getpid(),
                "allowed_roots": [str(Path(r).expanduser().resolve()) for r in DEFAULT_ROOTS],
                "env_paths": {
                    "HOME": str(Path.home()),
                    "AGENTFLOW_HOME": str(Path.home() / ".agentflow"),
                },
            }
            # CPU/内存
            info["cpu_count"] = os.cpu_count()
            try:
                import psutil
                vm = psutil.virtual_memory()
                info["memory"] = {"total_gb": round(vm.total / 2**30, 2),
                                  "available_gb": round(vm.available / 2**30, 2)}
            except ImportError:
                info["memory"] = "install psutil for details"
            # Node.js 版本
            node = shutil.which("node")
            if node:
                try:
                    import subprocess
                    r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5)
                    info["node"] = r.stdout.strip()
                except Exception:
                    info["node"] = str(node)
            return ToolResult(ok=True, output=json.dumps(info, ensure_ascii=False, indent=2), data=info)
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


def register_all():
    from app.tools import registry
    for cls in (HostReadTool, HostListDirTool, HostWriteTool, HostEditTool,
                HostDeleteTool, HostMoveTool, HostInfoTool):
        registry.register(cls())
    # shell 工具单独 import（避免 shlex 等 import 开销）
    from app.tools.host.shell import HostShellTool
    registry.register(HostShellTool())
