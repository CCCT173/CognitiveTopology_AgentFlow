"""
工具注册中心 v2
- BaseTool 支持同步/异步执行，分类 (builtin/platform/code/skill/mcp/workflow/host)，
  结构化 dict 返回，OpenAI function-calling / MCP tool 双序列化
- ToolRegistry 单例，按 type 过滤
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable


# Tool type 常量
TOOL_TYPE_BUILTIN = "builtin"      # 平台内置：rag_search/calculator/web_search/http_request
TOOL_TYPE_PLATFORM = "platform"    # L2 平台工具：create_workflow/add_node/run_workflow
TOOL_TYPE_CODE = "code"            # L3 code：run_code
TOOL_TYPE_SKILL = "skill"          # 用户 Skill
TOOL_TYPE_MCP = "mcp"              # 外部 MCP server
TOOL_TYPE_WORKFLOW = "workflow"    # 工作流节点/子工作流
TOOL_TYPE_HOST = "host"            # L0 主机访问：host_read/host_shell/...

ALL_TOOL_TYPES = {
    TOOL_TYPE_BUILTIN, TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE,
    TOOL_TYPE_SKILL, TOOL_TYPE_MCP, TOOL_TYPE_WORKFLOW, TOOL_TYPE_HOST,
}

# 默认暴露给 Agent 的工具类型（不暴露 platform/host，除非显式开启）
DEFAULT_VISIBLE_TYPES = {TOOL_TYPE_BUILTIN, TOOL_TYPE_CODE, TOOL_TYPE_SKILL, TOOL_TYPE_MCP, TOOL_TYPE_WORKFLOW}


class ToolResult:
    """结构化工具返回（替代纯 string）"""
    __slots__ = ("ok", "output", "error", "data", "requires_confirmation")

    def __init__(
        self,
        ok: bool = True,
        output: str = "",
        error: str | None = None,
        data: Any = None,
        requires_confirmation: bool = False,
    ):
        self.ok = ok
        self.output = output
        self.error = error
        self.data = data
        self.requires_confirmation = requires_confirmation

    def to_text(self) -> str:
        if not self.ok:
            return f"[error] {self.error}"
        return self.output or (str(self.data) if self.data is not None else "")

    def to_diag(self) -> dict:
        d = {"ok": self.ok}
        if self.output:
            d["output"] = self.output
        if self.error:
            d["error"] = self.error
        if self.data is not None:
            d["data"] = str(self.data)[:500]
        return d


class BaseTool:
    """所有工具的基类。子类实现 run() 或 arun()。"""
    name: str = ""
    display_name: str = ""
    description: str = ""
    params_schema: dict = {}
    tool_type: str = TOOL_TYPE_BUILTIN
    # 标记高危工具，调用前需要用户确认（复用 HITL）
    requires_confirmation: bool = False
    # 元数据（mcp_server、skill_id 等来源标记）
    metadata: dict = {}

    def run(self, ctx: Any = None, **kwargs) -> ToolResult | str | Any:
        """同步执行（子类实现）。接受可选 ctx（AgentContext）。"""
        raise NotImplementedError

    def __call__(self, **kwargs):
        """直接调用实例走 _run_sync 收敛异常和类型"""
        return self._run_sync(**kwargs)

    async def arun(self, ctx: Any = None, **kwargs) -> ToolResult:
        """异步执行；默认把同步 run() 丢线程池"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: self._run_sync(ctx=ctx, **kwargs))
        return self._to_result(result)

    def _run_sync(self, ctx=None, **kwargs):
        try:
            # 检查 run 是否接受 ctx 参数（兼容旧工具）
            try:
                r = self.run(ctx=ctx, **kwargs)
            except TypeError:
                r = self.run(**kwargs)
            return r
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")

    @staticmethod
    def _to_result(r: Any) -> ToolResult:
        if isinstance(r, ToolResult):
            return r
        if isinstance(r, str):
            return ToolResult(output=r)
        if isinstance(r, dict):
            return ToolResult(output=r.get("output", ""), data=r.get("data"))
        if r is None:
            return ToolResult(output="")
        return ToolResult(output=str(r))

    # ---- 序列化 ----
    def to_openai_schema(self) -> dict:
        """OpenAI function-calling schema"""
        schema = self.params_schema or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def to_mcp_tool(self) -> dict:
        """MCP tool 定义（inputSchema 是 MCP 术语）"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.params_schema or {"type": "object", "properties": {}},
        }


class ToolRegistry:
    """工具注册中心"""
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        if not tool.name:
            raise ValueError("tool.name 不能为空")
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list(self, tool_types: set[str] | None = None) -> list[BaseTool]:
        tools = list(self._tools.values())
        if tool_types is not None:
            tools = [t for t in tools if t.tool_type in tool_types]
        return tools

    def names(self, tool_types: set[str] | None = None) -> list[str]:
        return [t.name for t in self.list(tool_types)]

    def to_openai_tools(self, names: list[str] | None = None,
                        tool_types: set[str] | None = None) -> list[dict]:
        """转 OpenAI function-calling 格式"""
        out = []
        for t in self.list(tool_types):
            if names is not None and t.name not in names:
                continue
            out.append(t.to_openai_schema())
        return out

    def to_mcp_tools(self, tool_types: set[str] | None = None) -> list[dict]:
        return [t.to_mcp_tool() for t in self.list(tool_types)]


# ======== 全局单例 ========
registry = ToolRegistry()


def _autodiscover():
    """自动注册内置工具（延迟 import 防循环依赖）"""
    from app.tools.builtin import (  # noqa: F401
        rag_search, web_search, http_request, calculator, skill_tool,
    )
    from app.tools.code import run_code  # noqa: F401
    from app.tools.platform.workflows import register_all as _reg_wf
    _reg_wf()
    from app.tools.platform.agents_skills_kbs import register_all as _reg_ask
    _reg_ask()
    from app.tools.host import register_all as _reg_host
    _reg_host()


def get_registry() -> ToolRegistry:
    if not registry._tools:
        _autodiscover()
    return registry
