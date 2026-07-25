"""
MetaAgent - 能操控平台自身的 AI 代理
通过 ReAct 模式使用 L2 platform 工具 + run_code，让用户用自然语言
创建/修改/运行工作流、管理 agent 等。

高危工具（requires_confirmation=True）不会被 MetaAgent 直接执行，而是写入
PendingConfirmation 表并返回 confirmation_id 给前端，用户确认后才真正执行。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.agent_runtime.base import (
    AgentContext, RunResult,
)
from app.services.agent_runtime.react import ReActRunner
from app.tools import get_registry, TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN, ToolResult


META_SYSTEM_PROMPT = """你是 agentflow 平台的 AI 助手，可以帮助用户创建、修改、运行、查询工作流、Agent、技能和知识库。

## 可用工具
你可以使用以下类别工具：

### 1. 平台工具（platform）- 操控平台自身
- 工作流：list_workflows / get_workflow / create_workflow / update_workflow / delete_workflow
- Agent：list_agents / get_agent / create_agent / update_agent / delete_agent / toggle_agent
- 技能：list_skills / toggle_skill
- 知识库：list_knowledge_bases / kb_stats / create_knowledge_base / delete_knowledge_base

### 2. 代码执行（code）
- run_code：在沙箱里执行 Python 代码做数据分析/计算

### 3. 主机访问（host）- 读写宿主机文件
- host_read / host_list_dir / host_write / host_edit / host_delete / host_move / host_info / host_shell
- host_shell 执行只读命令自动放行，写命令需用户确认

### 4. 内置工具（builtin）
- calculator / rag_search / web_search / http_request

## 工作流 DSL 格式
工作流定义是 JSON：
```json
{
  "entry": "start_node_id",
  "nodes": [
    {"id": "n1", "type": "llm", "config": {"model": "...", "prompt": "..."}},
    {"id": "n2", "type": "tool", "config": {"tool_name": "calculator", "params": {...}}},
    {"id": "n3", "type": "condition", "config": {"expression": "score > 0.8"}},
    {"id": "n4", "type": "agent", "config": {"agent_name": "xxx"}},
    {"id": "n5", "type": "code", "config": {"code": "result = ..."}}
  ],
  "edges": [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}]
}
```
节点类型：start/end/llm/tool/skill/agent/condition/foreach/code/knowledge_retrieval/http

## 规则
- 创建/修改前先 list/get 了解现状
- 创建工作流/Agent/KB 时 name 必填
- DSL 结构要完整：entry + nodes + edges
- **删除操作（delete_workflow/delete_agent/delete_kb/host_write/host_delete/host_shell 写命令等）会触发用户确认，你调用后会收到 confirmation_id，告知用户等待确认**
- 结果用中文总结，给出 id 方便后续引用
- 错误信息如实转述给用户，不要编造
"""


@dataclass
class MetaAgent:
    """模拟一个 agent 对象，供 ReActRunner 使用。
    不走 DB agent 表，因为 MetaAgent 是系统内置。
    """
    id: int = 0
    name: str = "AI助手"
    system_prompt: str = META_SYSTEM_PROMPT
    model: str = ""            # 用默认
    provider: str = ""
    tools: list[str] = field(default_factory=list)
    rag_kb_ids: list[int] = field(default_factory=list)
    max_iterations: int = 20
    temperature: float = 0.2
    architecture: str = "react"
    enabled: bool = True


class MetaRunner(ReActRunner):
    """带 platform tools + HITL 的 ReAct Runner

    扩展 ReActRunner：在工具执行前检查 tool.requires_confirmation，
    如果是高危工具则创建 PendingConfirmation 并返回 confirmation_id，
    由前端触发用户确认流程。
    """

    def __init__(self, extra_tool_types: Iterable[str] | None = None,
                 hitl_mode: str = "auto"):
        """
        hitl_mode:
          - "auto": 高危工具走 HITL（生产默认）
          - "bypass": 忽略确认标记直接执行（测试/管理员场景）
        """
        self.extra_types = set(extra_tool_types or ())
        self.hitl_mode = hitl_mode
        # 本次 run 累积的待确认操作（供 API 层返回给前端）
        self.pending_confirmations: list[dict] = []

    def _execute_tool(self, tool, ctx, args):
        """拦截高危工具，写入 PendingConfirmation 而不真执行"""
        if tool.requires_confirmation and self.hitl_mode != "bypass":
            from app.services.hitl import create_confirmation
            risk_level = getattr(tool, "risk_level", "high")
            summary = self._describe_tool_call(tool.name, args)
            db = getattr(ctx, "db", None)
            if db is not None:
                pc = create_confirmation(
                    db,
                    user_id=getattr(ctx, "user_id", 0) or 0,
                    tool_name=tool.name,
                    args=args,
                    summary=summary,
                    risk_level=risk_level,
                    thread_id=getattr(ctx, "thread_id", "") or "",
                )
                self.pending_confirmations.append({
                    "confirmation_id": pc.id,
                    "tool_name": tool.name,
                    "summary": summary,
                    "risk_level": risk_level,
                })
                return (
                    f"[需要用户确认] 操作 '{tool.name}' 已提交为待确认任务 "
                    f"(id={pc.id})。请告知用户：{summary}。用户在前端点确认后会继续执行。"
                )
            # 没有 db session（理论不会发生），降级为执行
        return super()._execute_tool(tool, ctx, args)

    @staticmethod
    def _describe_tool_call(tool_name: str, args: dict) -> str:
        """生成给用户看的中文摘要"""
        if tool_name == "delete_workflow":
            wid = args.get("workflow_id", "?")
            return f"确认删除工作流 #{wid}？此操作不可恢复。"
        return f"确认执行 {tool_name}({', '.join(f'{k}={v}' for k, v in args.items())})？"

    def run(self, ctx: AgentContext) -> RunResult:
        self.pending_confirmations = []
        reg = get_registry()
        visible_types = {TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN} | self.extra_types
        visible_tools = reg.list(visible_types)
        ctx.agent.tools = [t.name for t in visible_tools]
        restore = None
        # 对高危工具注入 wrapper：run() 时创建 PendingConfirmation
        if self.hitl_mode != "bypass":
            restore = self._wrap_dangerous_tools(ctx, visible_tools)
        try:
            result = super().run(ctx)
        finally:
            if restore:
                restore()
        # 把 pending_confirmations 挂到 result 上（动态属性）
        result.pending_confirmations = list(self.pending_confirmations)
        return result

    def run_stream(self, ctx: AgentContext):
        """ReAct streaming 模式，yield SSE 事件。wrapper 在 generator 生命周期内生效。"""
        self.pending_confirmations = []
        reg = get_registry()
        visible_types = {TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN} | self.extra_types
        visible_tools = reg.list(visible_types)
        ctx.agent.tools = [t.name for t in visible_tools]
        restore = None
        if self.hitl_mode != "bypass":
            restore = self._wrap_dangerous_tools(ctx, visible_tools)
        try:
            for ev in super().run_stream(ctx):
                if ev.get("type") == "done":
                    ev["data"]["pending_confirmations"] = list(self.pending_confirmations)
                yield ev
        finally:
            if restore:
                restore()

    async def arun(self, ctx: AgentContext) -> RunResult:
        self.pending_confirmations = []
        reg = get_registry()
        visible_types = {TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN} | self.extra_types
        visible_tools = reg.list(visible_types)
        ctx.agent.tools = [t.name for t in visible_tools]
        restore = None
        if self.hitl_mode != "bypass":
            restore = self._wrap_dangerous_tools(ctx, visible_tools)
        try:
            result = await super().arun(ctx)
        finally:
            if restore:
                restore()
        result.pending_confirmations = list(self.pending_confirmations)
        return result

    def _wrap_dangerous_tools(self, ctx, visible_tools):
        """把 requires_confirmation=True 的工具替换为 wrapper 注入 registry；返回 restore 函数。

        实现：直接替换 registry._tools[name] 为 wrapper 实例；finally 时还原。
        并发安全：ReAct 循环是同步阻塞（OpenAI client 同步调用），run() 期间不会被打断。
        """
        from app.services.hitl import create_confirmation
        from app.tools import get_registry
        reg = get_registry()
        db = getattr(ctx, "db", None)
        user_id = getattr(ctx, "user_id", 0) or 0
        thread_id = getattr(ctx, "thread_id", "") or ""
        originals = {}

        for tool in visible_tools:
            if not tool.requires_confirmation:
                continue
            original = tool
            risk_level = getattr(tool, "risk_level", "high")
            describe = self._describe_tool_call

            class _Wrapper:
                """伪装成原工具，run() 时创建 PendingConfirmation 而不真执行"""
                def __init__(self, orig, runner_self):
                    self._orig = orig
                    self._runner = runner_self
                    self.name = orig.name
                    self.display_name = getattr(orig, "display_name", orig.name)
                    self.description = orig.description
                    self.params_schema = orig.params_schema
                    self.tool_type = orig.tool_type
                    self.requires_confirmation = False  # 已处理，ReAct 不会再包
                    self.metadata = getattr(orig, "metadata", {})

                def run(self, _ctx=None, **args):
                    summary = describe(original.name, args)
                    if db is None:
                        return original.run(ctx=_ctx, **args)
                    pc = create_confirmation(
                        db, user_id=user_id, tool_name=original.name, args=args,
                        summary=summary, risk_level=risk_level, thread_id=thread_id,
                    )
                    self._runner.pending_confirmations.append({
                        "confirmation_id": pc.id, "tool_name": original.name,
                        "summary": summary, "risk_level": risk_level,
                    })
                    return (
                        f"[需要用户确认] 操作 '{original.name}' 已提交为待确认任务 "
                        f"(id={pc.id})。请告知用户：{summary} 用户确认后会真正执行。"
                    )

                # 代理 schema 序列化方法给 OpenAI/MCP 格式
                def to_openai_schema(self):
                    return original.to_openai_schema()

                def to_mcp_tool(self):
                    return original.to_mcp_tool()

            wrapper = _Wrapper(original, self)
            originals[original.name] = original
            reg._tools[original.name] = wrapper

        def _restore():
            for name, orig in originals.items():
                reg._tools[name] = orig

        return _restore


def build_meta_context(message: str, db=None, user_id: int = 1,
                       history: list[dict] | None = None,
                       thread_id: str = "meta",
                       model_override: str | None = None) -> AgentContext:
    """构造 MetaAgent 专用的 AgentContext"""
    agent = MetaAgent(model=model_override or "")
    return AgentContext(
        agent=agent,
        message=message,
        user_id=user_id,
        thread_id=thread_id,
        history=history or [],
        db=db,
    )
