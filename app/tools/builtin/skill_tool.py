"""把 Skill 类型的 Agent 包装成可被其他 Agent 调用的工具"""
from __future__ import annotations
from typing import Any
from app.tools import BaseTool
from app.services.agent_runtime import AgentContext
from app.services.agent_runtime.simple import SimpleRunner


class SkillAsTool(BaseTool):
    """把一个 architecture=skill 的 Agent 包装成工具。
    工具名: skill_<agent.name>
    参数: {"message": "传给这个专家的问题"}
    """

    def __init__(self, skill_agent):
        self._agent = skill_agent
        self.name = f"skill_{skill_agent.name}"
        self.display_name = skill_agent.display_name or skill_agent.name
        self.description = skill_agent.description or f"调用专家 {skill_agent.name} 处理问题"
        self.params_schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "要交给这个专家处理的问题/任务"},
            },
            "required": ["message"],
        }

    def run(self, ctx: Any, **kwargs) -> str:
        message = kwargs.get("message", "").strip()
        if not message:
            return "[skill] message 不能为空"
        # 用 SimpleRunner 在同一上下文里执行该 skill
        sub_ctx = AgentContext(
            db=ctx.db,
            user_id=ctx.user_id,
            agent=self._agent,
            message=message,
            thread_id=ctx.thread_id,
            variables=ctx.variables,
            history=[],  # skill 内部独立,不继承父历史
        )
        runner = SimpleRunner()
        result = runner.run(sub_ctx)
        return result.reply


def collect_skill_tools(db, parent_agent_id: int | None = None) -> list[BaseTool]:
    """查询可用的 skill agent,包装成工具。
    - parent_agent_id: 只返回归属于该父 agent 的 skill;None 则返回全部 skill
    """
    from sqlalchemy import select
    from app.models.agent import Agent as AgentModel
    stmt = select(AgentModel).where(AgentModel.architecture == "skill", AgentModel.enabled.is_(True))
    if parent_agent_id is not None:
        stmt = stmt.where(AgentModel.parent_agent_id == parent_agent_id)
    skills = db.scalars(stmt).all()
    return [SkillAsTool(s) for s in skills]
