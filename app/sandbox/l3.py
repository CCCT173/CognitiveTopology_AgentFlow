"""
L3 Code Interpreter - 子进程模式（简化版）
- 专用 venv，预装 numpy/pandas 等数据科学包
- 工作目录隔离（~/.agentflow/ws/{session_id}/）
- 内置 workspace API（read/write/list_dir 带路径校验）
- fetch 直接用 httpx（代码解释器信任用户代码）
- 产物回流：用户代码把结果赋给 result 变量，父进程拿到 L3Result 后由调用方决定是否回流
- 超时 60s，stdout/stderr 1MB 上限
- Windows subprocess fallback；Docker 模式后续实现
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WS_ROOT = Path.home() / ".agentflow" / "ws"
WS_ROOT.mkdir(parents=True, exist_ok=True)

VENV_DIR = Path.home() / ".agentflow" / "venv_l3"

DEFAULT_PACKAGES = [
    "numpy", "pandas", "openpyxl", "pypdf", "python-docx",
    "beautifulsoup4", "matplotlib", "pillow", "requests",
    "jinja2", "pyyaml", "tiktoken", "httpx",
]

DEFAULT_TIMEOUT_SEC = 60
MAX_OUTPUT_BYTES = 1024 * 1024  # 1MB


@dataclass
class L3Result:
    ok: bool
    output: Any = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    files_created: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "output": self.output,
            "stdout": self.stdout, "stderr": self.stderr,
            "error": self.error, "files_created": self.files_created,
        }


def ensure_venv() -> Path:
    """确保 L3 venv 存在并装好默认包。返回 python 可执行文件路径。"""
    py_path = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if py_path.exists():
        return py_path
    import venv as _venv_mod
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    _venv_mod.EnvBuilder(with_pip=True, clear=False).create(str(VENV_DIR))
    subprocess.run(
        [str(py_path), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"] + DEFAULT_PACKAGES,
        check=False, capture_output=True, timeout=600,
    )
    return py_path


def _ws_dir(session_id: str) -> Path:
    p = WS_ROOT / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


# -------- 子进程 runner --------
_RUNNER_CODE = r'''
import sys, os, json, io, traceback
from contextlib import redirect_stdout, redirect_stderr

# 资源限制（Unix）；Windows 上 resource 不存在，靠父进程 timeout 兜底
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (50, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**31))
    resource.setrlimit(resource.RLIMIT_NPROC, (100, 200))
    resource.setrlimit(resource.RLIMIT_FSIZE, (100*1024*1024, -1))
except Exception:
    pass

WS_DIR = os.environ["L3_WS_DIR"]
os.chdir(WS_DIR)
sys.path.insert(0, WS_DIR)

class Workspace:
    """用户代码可调用的工作区 API"""
    @staticmethod
    def _resolve(path):
        p = os.path.realpath(os.path.join(WS_DIR, path))
        if not p.startswith(os.path.realpath(WS_DIR) + os.sep) and p != os.path.realpath(WS_DIR):
            raise ValueError(f"路径越界: {path}")
        return p
    @staticmethod
    def read(path, encoding="utf-8"):
        return open(Workspace._resolve(path), "r", encoding=encoding).read()
    @staticmethod
    def write(path, content, mode="w", encoding="utf-8"):
        p = Workspace._resolve(path)
        os.makedirs(os.path.dirname(p) or WS_DIR, exist_ok=True)
        open(p, mode, encoding=encoding).write(content)
    @staticmethod
    def list_dir(path="."):
        return sorted(os.listdir(Workspace._resolve(path)))
    @staticmethod
    def exists(path):
        return os.path.exists(Workspace._resolve(path))
    @staticmethod
    def fetch(url, **kw):
        import requests as _rq
        headers = kw.get("headers")
        method = kw.get("method", "GET").upper()
        timeout = kw.get("timeout", 30)
        body = kw.get("body")
        r = _rq.request(method, url, headers=headers, data=body, timeout=timeout)
        return r.text
    @staticmethod
    def install_pkg(name: str):
        """在 L3 venv 里安装额外 pip 包（只限 PyPI）"""
        import subprocess as _sp
        import sys as _sys
        # 黑名单：禁止从 git/URL/本地路径安装
        if any(c in name for c in ("git+", "http://", "https://", "/", "\\", "-e ", ".")):
            raise ValueError(f"不安全的包名: {name}")
        py = _sys.executable
        r = _sp.run([py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", name],
                    capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"pip install 失败: {r.stderr[-300:]}")
        return f"安装 {name} 成功"

workspace = Workspace()
ws = workspace

def main():
    payload = json.loads(sys.stdin.read())
    code = payload.get("code", "")
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    result = {"ok": False, "output": None, "stdout": "", "stderr": "", "error": None, "files": []}
    try:
        ns = {"__name__": "__main__", "workspace": workspace, "ws": workspace}
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<l3-code>", "exec"), ns)
            output = ns.get("_result", ns.get("result"))
        files = []
        for root, _, fns in os.walk(WS_DIR):
            for fn in fns:
                files.append(os.path.relpath(os.path.join(root, fn), WS_DIR))
        result["ok"] = True
        result["output"] = output
        result["files"] = sorted(files)[:50]
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc(limit=3)
    result["stdout"] = stdout_buf.getvalue()
    result["stderr"] = stderr_buf.getvalue()
    sys.stdout.write(json.dumps(result, default=str, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''


def run_l3(code: str, session_id: str = "default", timeout: int = DEFAULT_TIMEOUT_SEC,
            inputs: dict | None = None) -> L3Result:
    """在 L3 沙箱执行 Python 代码"""
    py = ensure_venv()
    ws = _ws_dir(session_id)
    env = os.environ.copy()
    env["L3_WS_DIR"] = str(ws)
    env["PYTHONUNBUFFERED"] = "1"
    payload = json.dumps({"code": code, "timeout": timeout, "inputs": inputs or {}}, ensure_ascii=False)
    proc = subprocess.Popen(
        [str(py), "-u", "-c", _RUNNER_CODE],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=env, cwd=str(ws),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    try:
        out, err = proc.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try: out, err = proc.communicate(timeout=3)
        except Exception: out, err = "", ""
        return L3Result(ok=False, error=f"执行超时 (>{timeout}s)")
    try:
        data = json.loads(out.strip()) if out.strip() else {"ok": False, "error": "无输出"}
    except json.JSONDecodeError:
        data = {"ok": False, "error": f"输出非 JSON: {out[:300]}", "stdout": out, "stderr": err}
    return L3Result(
        ok=data.get("ok", False),
        output=data.get("output"),
        stdout=str(data.get("stdout", ""))[:MAX_OUTPUT_BYTES],
        stderr=(str(data.get("stderr", "")) + err)[:MAX_OUTPUT_BYTES].strip(),
        error=data.get("error"),
        files_created=data.get("files", []),
    )


def reset_session(session_id: str):
    ws = WS_ROOT / session_id
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)


async def arun_l3(code: str, session_id: str = "default", timeout: int = DEFAULT_TIMEOUT_SEC,
                  inputs: dict | None = None) -> L3Result:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: run_l3(code, session_id, timeout, inputs))
