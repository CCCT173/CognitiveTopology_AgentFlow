"""
Agent 运行时
- BaseRunner: 所有架构 Runner 的抽象基类
- SimpleRunner / ReActRunner / WorkflowRunner / SkillRunner
- get_runner(architecture): 工厂方法, 根据 architecture 字段返回对应 Runner
- AgentContext: 运行时上下文 (db/user/agent/memory/tools/...)

工作分工:
  Agent  = 执行者,负责单体智能(LLM/工具调用/推理)
  Workflow = 编排者,多步骤/多角色/分支/人工介入

调用流程:
  chat_service.chat() -> runtime.get_runner(agent.architecture).run(ctx)
"""
from app.services.agent_runtime.base import BaseRunner, AgentContext, RunResult
from app.services.agent_runtime.simple import SimpleRunner
from app.services.agent_runtime.react import ReActRunner
from app.services.agent_runtime.workflow_runner import WorkflowRunner
from app.services.agent_runtime.skill_runner import SkillRunner

_RUNNERS: dict[str, BaseRunner] = {}


def _register():
    if _RUNNERS:
        return
    _RUNNERS["single"] = SimpleRunner()
    _RUNNERS["react"] = ReActRunner()
    _RUNNERS["workflow"] = WorkflowRunner()
    _RUNNERS["skill"] = SkillRunner()


def get_runner(architecture: str) -> BaseRunner:
    _register()
    runner = _RUNNERS.get((architecture or "single").lower())
    if not runner:
        # 未知架构默认降级为 simple
        runner = _RUNNERS["single"]
    return runner


__all__ = [
    "BaseRunner", "AgentContext", "RunResult",
    "SimpleRunner", "ReActRunner", "WorkflowRunner", "SkillRunner",
    "get_runner",
]
