"""run_code 工具：调用 L3 Code Interpreter 执行 Python 代码"""
from __future__ import annotations
from typing import Any
from app.tools import BaseTool, ToolResult, TOOL_TYPE_CODE
from app.sandbox.l3 import run_l3, DEFAULT_TIMEOUT_SEC


class RunCodeTool(BaseTool):
    name = "run_code"
    display_name = "执行 Python 代码"
    tool_type = TOOL_TYPE_CODE
    description = (
        "在沙箱中执行 Python 代码并返回结果。用于数据分析、计算、文件处理、网页抓取等。"
        "代码可通过 workspace.read/write/list_dir 读写会话工作目录的文件，"
        "workspace.fetch(url) 抓取网页，workspace.install_pkg(name) 临时安装 PyPI 包。"
        "结果写入 result 变量。预装 numpy/pandas/matplotlib/requests/openpyxl/pypdf 等。"
        "代码运行最长 60 秒，无法访问宿主文件系统（仅限沙箱工作目录）。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 源码。把最终结果赋给 result 变量。",
            },
            "session_id": {
                "type": "string",
                "description": "会话 id，同 id 共享工作目录和已安装的包。留空则用 'default'。",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数（1-120），默认 60",
                "minimum": 1,
                "maximum": 120,
            },
        },
        "required": ["code"],
    }

    def run(self, ctx: Any = None, **kwargs) -> ToolResult:
        code = kwargs.get("code", "").strip()
        if not code:
            return ToolResult(ok=False, error="code 不能为空")
        session_id = kwargs.get("session_id") or "default"
        timeout = min(max(int(kwargs.get("timeout", DEFAULT_TIMEOUT_SEC)), 1), 120)
        res = run_l3(code=code, session_id=session_id, timeout=timeout)
        output_text = ""
        if res.stdout:
            output_text += f"[stdout]\n{res.stdout}\n"
        if res.stderr:
            output_text += f"[stderr]\n{res.stderr}\n"
        if res.ok:
            output_text += f"[result] {res.output!r}"
            return ToolResult(
                ok=True,
                output=output_text.strip(),
                data={"result": res.output, "files": res.files_created},
            )
        return ToolResult(ok=False, output=output_text.strip(), error=res.error)


# 注册到全局 registry
from app.tools import registry  # noqa: E402
registry.register(RunCodeTool())
