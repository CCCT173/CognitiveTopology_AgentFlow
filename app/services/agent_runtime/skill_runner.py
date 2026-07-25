"""SkillRunner: 技能型子 Agent
不能被用户直接对话(API 层拦截),只能作为工具被其他 Agent 调用。
使用场景: 把"专家能力"(例:法律问答/代码审查/翻译)模块化,被父 Agent 或 workflow 复用。
实现上: Skill Agent 本身的执行逻辑等价于 SimpleRunner,只是权限受限。
"""
from app.services.agent_runtime.base import BaseRunner, AgentContext, RunResult
from app.services.agent_runtime.simple import SimpleRunner


class SkillRunner(SimpleRunner):
    architecture = "skill"

    def run(self, ctx: AgentContext) -> RunResult:
        # Skill 和 single 执行方式相同, 只是不能被用户直接对话(由 chat_service 校验拦截)
        return super().run(ctx)
