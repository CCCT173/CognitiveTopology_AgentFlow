"""WorkflowRunner: 工作流入口
Agent 本身不做推理, 而是触发 workflow_service.run_workflow()
适用于: 企业流程、多分支/循环/并行、人工介入、多Agent 协作
Agent 必须关联 workflow_id (或通过 name 找到 workflow), 否则返回错误
framework 字段决定走哪个 runtime:
  - ""         : 内部简单图执行 (workflow_service.run_workflow, DAG执行)
  - "langgraph": LangGraph StateGraph (预留)
  - "crewai"   : CrewAI Flow/Crew (预留)
  - "autogen"  : AutoGen GroupChat (预留)
"""
from app.core.exceptions import ErrBadRequest
from app.services.agent_runtime.base import BaseRunner, AgentContext, RunResult
from app.services import workflow_service
from app.schemas.workflow import WorkflowRunIn


class WorkflowRunner(BaseRunner):
    architecture = "workflow"

    def run(self, ctx: AgentContext) -> RunResult:
        from app.models.workflow import Workflow
        from sqlalchemy import select

        agent = ctx.agent
        wf_id = getattr(agent, "workflow_id", None)
        wf = None

        if wf_id:
            wf = ctx.db.get(Workflow, wf_id)
        if not wf:
            # fallback: 按 agent.name 匹配同名 workflow
            wf = ctx.db.scalar(select(Workflow).where(Workflow.name == agent.name))
        if not wf:
            raise ErrBadRequest(
                f"Agent {agent.name} 是 workflow 架构但未关联任何工作流。"
                f"请在 Agent 编辑页设置 workflow_id, 或创建同名 workflow。"
            )

        framework = (getattr(agent, "framework", "") or "").strip().lower()
        if framework and framework not in ("", "internal", "simple"):
            raise ErrBadRequest(f"暂未支持 framework={framework!r}, 目前仅内置 DAG 执行器")

        # 构造输入: 优先用 ctx.variables, 否则用 ctx.message
        input_data: dict = {}
        if ctx.variables:
            input_data.update(ctx.variables)
        if ctx.message:
            input_data.setdefault("input", ctx.message)
            input_data.setdefault("message", ctx.message)

        result = workflow_service.run_workflow(
            ctx.db, wf.id,
            WorkflowRunIn(input=input_data, variables=input_data),
        )

        # 组装 steps (供前端展示执行细节)
        steps = [{
            "iter": 0, "action": "workflow_start",
            "tool": f"workflow:{wf.name}",
            "args": {"input": input_data},
            "result": f"run_id={result.get('run_id')}, elapsed={result.get('elapsed_ms')}ms, status={result.get('status')}",
        }]
        logs = result.get("logs") or []
        for line in logs:
            if line.startswith("▶") or line.startswith("  ↳"):
                steps.append({"iter": 0, "action": "log", "tool": "", "args": {}, "result": line.strip()})

        reply = result.get("output")
        if isinstance(reply, (dict, list)):
            import json
            reply = json.dumps(reply, ensure_ascii=False, indent=2)
        elif reply is None:
            reply = "(工作流无输出)"
        reply = str(reply)

        if result.get("error"):
            reply = f"⚠️ 工作流执行失败: {result['error']}\n\n{reply}"

        return RunResult(reply=reply, steps=steps, citations=list(getattr(ctx, "citations", []) or []))
