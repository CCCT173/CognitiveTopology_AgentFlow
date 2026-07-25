"""Runner 基类 + 运行时上下文"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from sqlalchemy.orm import Session


@dataclass
class AgentContext:
    """Agent 运行一次对话所需的全部上下文"""
    db: Session
    user_id: int
    agent: Any                        # ORM Agent 实例
    message: str                      # 用户本轮消息
    thread_id: str                    # 会话 id
    variables: dict = field(default_factory=dict)  # 额外变量
    history: list[dict] = field(default_factory=list)  # 历史消息 [{role,content}]
    # 工具调用时累积的结构化引用(RAG 检索片段等),runner 结束时会写入 RunResult.citations
    citations: list[dict] = field(default_factory=list)


@dataclass
class RunResult:
    """Runner 返回结果"""
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)  # ReAct/工作流中间步骤
    citations: list[dict] = field(default_factory=list)  # 结构化引用来源 [{idx,document_id,document_name,chunk_id,content,score}]


class BaseRunner:
    """所有架构 Runner 的抽象基类"""

    architecture: str = "base"

    def run(self, ctx: AgentContext) -> RunResult:
        """执行一次对话,返回 RunResult (同步)。"""
        raise NotImplementedError

    async def async_run(self, ctx: AgentContext) -> RunResult:
        """执行一次对话,返回 RunResult (异步)。默认调用同步 run()，子类可重写。"""
        return self.run(ctx)


def collect_tools(ctx: AgentContext) -> tuple[list[dict] | None, dict[str, Any]]:
    """收集 agent 可用工具: agent.tools + rag_search(若绑定KB) + skill工具。
    返回 (openai_tools, tool_map)。"""
    from app.tools import get_registry
    reg = get_registry()
    tool_names = list(ctx.agent.tools or [])
    if ctx.agent.rag_kb_ids and "rag_search" not in tool_names:
        tool_names.append("rag_search")
    openai_tools = reg.to_openai_tools(tool_names) if tool_names else None
    tool_map = {t.name: t for t in reg.list() if t.name in tool_names}
    from app.tools.builtin.skill_tool import collect_skill_tools
    for st in collect_skill_tools(ctx.db, parent_agent_id=ctx.agent.id):
        openai_tools = openai_tools or []
        openai_tools.append({
            "type": "function",
            "function": {"name": st.name, "description": st.description, "parameters": st.params_schema},
        })
        tool_map[st.name] = st
    return openai_tools, tool_map


def msg_to_dict(msg) -> dict:
    """OpenAI response message -> dict(可重新喂给 API)"""
    d = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return d
