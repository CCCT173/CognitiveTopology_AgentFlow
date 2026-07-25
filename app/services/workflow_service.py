"""
工作流 CRUD + DAG 执行引擎
- definition 结构:
    {
      "nodes": [{"id": "n1", "type": "start|end|llm|tool|skill|condition|agent", "name": "...", "config": {...}, "position": {x,y}}],
      "edges": [{"id":"e1","source":"n1","target":"n2","sourceHandle":"...","condition":"..."}],
      "entry": "n1"
    }
- 支持的节点类型:
    start      : 接收输入
    end        : 返回输出
    llm        : 调用 LLM, config.prompt(支持 {{var}} 模板)
    tool       : 调用注册工具, config.tool_name, config.params
    skill      : 调用 Skill 表中技能, config.skill_id/config.skill_name, config.params
    condition  : 按 config.expression (jinja-like) 判断, edges.condition 标记分支(truthy/falsy 或 key=value)
    agent      : 调用已存在 agent, config.agent_name, config.message
- 变量透传: 每个节点的输出写入 context[node_id], 后续节点可通过 {{node_id.field}} 引用
- 按拓扑排序执行, 检测环
"""
from __future__ import annotations
import json
import re
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workflow import Workflow, WorkflowRun
from app.models.user import User
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowRunIn
from app.core.exceptions import ErrNotFound, ErrConflict, ErrBadRequest
from app.core.logger import logger


# 全局内存存储正在执行的工作流结果（用于异步执行时快速查询）
_workflow_results: dict[str, dict] = {}



# ---------- CRUD ----------
def list_workflows(db: Session, keyword: str | None = None, category: str | None = None,
                   owner_id: int | None = None, enabled_only: bool = False) -> list[Workflow]:
    stmt = select(Workflow)
    if keyword:
        stmt = stmt.where(Workflow.name.ilike(f"%{keyword}%"))
    if category:
        stmt = stmt.where(Workflow.category == category)
    if owner_id is not None:
        stmt = stmt.where(Workflow.user_id == owner_id)
    if enabled_only:
        stmt = stmt.where(Workflow.enabled.is_(True))
    return list(db.scalars(stmt.order_by(Workflow.id.desc())).all())


def get_workflow(db: Session, wf_id: int) -> Workflow:
    obj = db.get(Workflow, wf_id)
    if not obj:
        raise ErrNotFound(f"工作流 {wf_id} 不存在")
    return obj


def get_workflow_by_name(db: Session, name: str) -> Workflow | None:
    return db.scalar(select(Workflow).where(Workflow.name == name))


def create_workflow(db: Session, user: User, body: WorkflowCreate) -> Workflow:
    if get_workflow_by_name(db, body.name):
        raise ErrConflict(f"工作流 '{body.name}' 已存在")
    obj = Workflow(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        category=body.category,
        definition=body.definition,
        user_id=user.user_id,
        created_by=user.user_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_workflow(db: Session, wf_id: int, body: WorkflowUpdate) -> Workflow:
    obj = get_workflow(db, wf_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_workflow(db: Session, wf_id: int) -> None:
    obj = get_workflow(db, wf_id)
    db.delete(obj)
    db.commit()


def toggle_workflow(db: Session, wf_id: int, enabled: bool) -> Workflow:
    obj = get_workflow(db, wf_id)
    obj.enabled = enabled
    db.commit()
    db.refresh(obj)
    return obj


# ---------- DAG 执行引擎 ----------
_VAR_RE = re.compile(r"\{\{\s*([\w\.\[\]\"']+?)\s*\}\}")


def _resolve_path(ctx: dict, path: str) -> Any:
    """解析 a.b.c 或 a['b'] 形式的路径"""
    # 简单拆分: 先处理点号, 再剥掉引号括号
    tokens: list[str] = []
    for part in path.split("."):
        # 处理 ['xxx'] / ["xxx"] 形式
        m = re.findall(r"([A-Za-z_]\w*)|\[['\"]?([^'\"]+)['\"]?\]", part)
        for g1, g2 in m:
            tokens.append(g1 or g2)
    v: Any = ctx
    for t in tokens:
        if v is None:
            return None
        if isinstance(v, dict):
            v = v.get(t)
        elif isinstance(v, (list, tuple)):
            try:
                v = v[int(t)]
            except (ValueError, IndexError):
                return None
        else:
            v = getattr(v, t, None)
    return v


def _render(value: Any, ctx: dict) -> Any:
    """递归渲染字符串中的 {{var}} 模板"""
    if isinstance(value, str):
        def _sub(m: re.Match) -> str:
            path = m.group(1).strip()
            try:
                v = _resolve_path(ctx, path)
                return "" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
            except Exception:
                return m.group(0)
        # 如果整个字符串就是单个 {{...}} 且不包含其他字符, 保留原始类型
        m_single = re.fullmatch(r"\{\{\s*([\w\.\[\]\"']+?)\s*\}\}", value.strip())
        if m_single and value.strip() == value:
            v = _resolve_path(ctx, m_single.group(1).strip())
            if not isinstance(v, str):
                return v if v is not None else ""
        return _VAR_RE.sub(_sub, value)
    if isinstance(value, list):
        return [_render(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, ctx) for k, v in value.items()}
    return value


def _topo_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """拓扑排序, 返回节点 id 序列; 检测环"""
    in_deg: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)
    ids = {n["id"] for n in nodes}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in ids and t in ids:
            adj[s].append(t)
            in_deg[t] += 1
    q = deque([n["id"] for n in nodes if in_deg[n["id"]] == 0])
    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            in_deg[v] -= 1
            if in_deg[v] == 0:
                q.append(v)
    if len(order) != len(nodes):
        raise ErrBadRequest("工作流存在环, 无法执行")
    return order


def _exec_node(node: dict, ctx: dict, db: Session, logs: list[str]) -> Any:
    """执行单个节点, 返回节点输出"""
    ntype = node.get("type", "")
    cfg = node.get("config") or {}
    nid = node.get("id", "?")
    name = node.get("name") or nid
    logs.append(f"▶ [{ntype}] {name}")

    try:
        if ntype == "start":
            # 透传输入
            return {"input": ctx.get("__input__", {})}

        if ntype == "end":
            # 输出指定字段
            out_key = cfg.get("output_key")
            if out_key:
                rendered = _render(out_key, ctx)
                return {"output": rendered}
            # 否则返回整个上下文(不含内部)
            return {"output": {k: v for k, v in ctx.items() if not k.startswith("__")}}

        if ntype == "llm":
            return _exec_llm(cfg, ctx, logs)

        if ntype == "tool":
            return _exec_tool(cfg, ctx, db, logs)

        if ntype == "skill":
            return _exec_skill_node(cfg, ctx, db, logs)

        if ntype == "agent":
            return _exec_agent_node(cfg, ctx, db, logs)

        if ntype == "condition":
            expr = cfg.get("expression", "")
            rendered = _render("{{ " + expr + " }}", ctx) if expr else ""
            # 用 simpleeval 做安全求值（替换裸 eval __builtins__={}，后者仍可元类逃逸）
            from app.core.safe_eval import safe_eval_bool
            result = safe_eval_bool(rendered, names=ctx)
            logs.append(f"  ↳ 条件结果: {result}")
            return {"condition_result": result, "value": rendered}

        logs.append(f"  ⚠ 未知节点类型: {ntype}, 跳过")
        return None
    except Exception as e:
        logger.exception(f"节点 {nid} 执行失败")
        logs.append(f"  ❌ 失败: {e}")
        raise


def _exec_llm(cfg: dict, ctx: dict, logs: list[str]) -> dict:
    """执行 LLM 节点。支持节点级 provider/model/top_p/penalties/response_format。"""
    from app.services.llm import _client_for, _resolve_provider_model
    from app.core.config import settings

    # 构造一个"伪 agent"对象复用 _resolve_provider_model 逻辑
    class _NCfg:
        def __init__(self, c):
            self.llm_config = c
    node_cfg = dict(cfg)
    # temperature 默认值与前端默认 0.7 对齐
    node_cfg.setdefault("temperature", 0.7)
    node_cfg.setdefault("stream", False)
    provider, model, kwargs = _resolve_provider_model(_NCfg(node_cfg))
    client = _client_for(provider)
    # 去掉 stream/thinking 等非 create 参数干扰
    kwargs.pop("stream", None)
    kwargs.pop("thinking", None)

    prompt_tpl = cfg.get("prompt", "{{input}}")
    sys_prompt = cfg.get("system_prompt", "")
    prompt = _render(prompt_tpl, ctx)
    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": _render(sys_prompt, ctx)})
    messages.append({"role": "user", "content": prompt})

    # response_format
    rf = cfg.get("response_format")
    create_kwargs = dict(kwargs)
    if rf == "json_object":
        create_kwargs["response_format"] = {"type": "json_object"}

    t0 = time.time()
    resp = client.chat.completions.create(
        model=model, messages=messages, stream=False, **create_kwargs,
    )
    text = resp.choices[0].message.content or ""
    elapsed = int((time.time() - t0) * 1000)
    logs.append(f"  ↳ LLM 响应 [{provider}/{model}] ({elapsed}ms, {len(text)} 字)")
    return {"text": text, "elapsed_ms": elapsed, "provider": provider, "model": model}


def _exec_tool(cfg: dict, ctx: dict, db: Session, logs: list[str]) -> dict:
    tool_name = cfg.get("tool_name", "")
    params = _render(cfg.get("params", {}) or {}, ctx)
    from app.tools import get_registry
    from app.services.agent_runtime import AgentContext
    reg = get_registry()
    tool = reg.get(tool_name)
    if not tool:
        raise ErrBadRequest(f"工具 '{tool_name}' 未注册")
    actx = AgentContext(db=db, user_id=0, agent=None, message="", thread_id="", variables={}, history=[])
    t0 = time.time()
    try:
        result = tool.run(ctx=actx, **params)
    except Exception as e:
        result = f"[工具执行失败: {e}]"
    elapsed = int((time.time() - t0) * 1000)
    logs.append(f"  ↳ 工具 {tool_name} ({elapsed}ms)")
    return {"result": result, "elapsed_ms": elapsed}


def _exec_skill_node(cfg: dict, ctx: dict, db: Session, logs: list[str]) -> dict:
    skill_id = cfg.get("skill_id")
    from app.models.skill import Skill
    from app.schemas.skill import SkillTestRequest
    skill = db.get(Skill, skill_id) if skill_id else None
    if not skill:
        sname = cfg.get("skill_name", "")
        skill = db.scalar(select(Skill).where(Skill.name == sname))
    if not skill:
        raise ErrBadRequest("Skill 不存在或未指定")
    params = _render(cfg.get("params", {}) or {}, ctx)
    from app.services.skill_service import SkillService
    t0 = time.time()
    req = SkillTestRequest(input_params=params, context=None)
    res = SkillService.test_skill(db, skill, req)
    elapsed = int((time.time() - t0) * 1000)
    logs.append(f"  ↳ Skill {skill.name} ({elapsed}ms)")
    return {"output": res.get("output"), "elapsed_ms": elapsed, "success": res.get("success")}


def _exec_agent_node(cfg: dict, ctx: dict, db: Session, logs: list[str]) -> dict:
    agent_name = cfg.get("agent_name", "")
    message = _render(cfg.get("message", "{{input}}"), ctx)
    from app.models.agent import Agent as AgentModel
    agent = db.scalar(select(AgentModel).where(AgentModel.name == agent_name))
    if not agent:
        raise ErrBadRequest(f"Agent '{agent_name}' 不存在")
    from app.services.agent_runtime import get_runner, AgentContext
    runner = get_runner(agent.architecture)
    t0 = time.time()
    actx = AgentContext(
        db=db, user_id=0, agent=agent,
        message=message, thread_id="",
        variables={}, history=[],
    )
    try:
        result = runner.run(actx)
        reply = result.reply
    except Exception as e:
        reply = f"[错误] {e}"
    elapsed = int((time.time() - t0) * 1000)
    logs.append(f"  ↳ Agent {agent_name} ({elapsed}ms)")
    return {"reply": reply, "elapsed_ms": elapsed}


def run_workflow(db: Session, wf_id: int, body: WorkflowRunIn, user_id: int = 0) -> dict:
    """执行工作流主入口"""
    wf = get_workflow(db, wf_id)
    if not wf.enabled:
        raise ErrBadRequest(f"工作流 '{wf.name}' 已禁用")
    definition = wf.definition or {}
    nodes = definition.get("nodes") or []
    edges = definition.get("edges") or []
    entry = definition.get("entry") or (nodes[0]["id"] if nodes else None)
    if not nodes or not entry:
        raise ErrBadRequest("工作流定义为空")

    run_id = uuid.uuid4().hex[:12]
    logs: list[str] = [f"🚀 工作流 {wf.name} (run_id={run_id}) 开始执行"]
    t0 = time.time()
    ctx: dict = {"__input__": body.input or body.variables or {}}
    node_map = {n["id"]: n for n in nodes}

    # 持久化运行记录 (running 状态)
    run_rec = WorkflowRun(
        run_id=run_id, workflow_id=wf.id, workflow_name=wf.name, user_id=user_id,
        status="running", input_data=body.input or body.variables or {}, logs=logs,
    )
    db.add(run_rec); db.commit(); db.refresh(run_rec)

    # 拓扑排序
    try:
        order = _topo_sort(nodes, edges)
    except ErrBadRequest:
        raise
    logs.append(f"📐 执行顺序: {' → '.join(order)}")

    outputs: dict = {}
    error: str | None = None
    status = "success"

    try:
        visited = set()
        executed: list[str] = []
        for nid in order:
            node = node_map.get(nid)
            if not node:
                continue
            if not _is_reachable(nid, entry, edges, outputs):
                continue
            executed.append(nid)
            out = _exec_node(node, ctx, db, logs)
            outputs[nid] = out
            ctx[nid] = out
            if node.get("type") == "end":
                break
        logs.append(f"✅ 共执行 {len(executed)} 个节点")
    except Exception as e:
        error = str(e)
        status = "failed"
        logs.append(f"❌ 工作流异常终止: {error}")

    elapsed = int((time.time() - t0) * 1000)
    final_output = None
    for n in nodes:
        if n.get("type") == "end" and n["id"] in outputs:
            final_output = outputs[n["id"]].get("output")
            break
    if final_output is None and outputs:
        last = list(outputs.values())[-1]
        final_output = last
    logs.append(f"⏱ 总耗时 {elapsed}ms, 状态 {status}")

    # 更新运行记录
    run_rec.status = status
    run_rec.output_data = final_output if isinstance(final_output, dict) else {"result": final_output}
    run_rec.logs = logs
    run_rec.node_outputs = outputs
    run_rec.error = error
    run_rec.elapsed_ms = elapsed
    db.commit()

    return {
        "run_id": run_id,
        "status": status,
        "output": final_output,
        "error": error,
        "logs": logs,
        "elapsed_ms": elapsed,
        "node_outputs": outputs,
    }


# ---------- 运行历史查询 ----------
def list_runs(db: Session, wf_id: int | None = None, limit: int = 50) -> list[WorkflowRun]:
    stmt = select(WorkflowRun)
    if wf_id is not None:
        stmt = stmt.where(WorkflowRun.workflow_id == wf_id)
    return list(db.scalars(stmt.order_by(WorkflowRun.id.desc()).limit(limit)).all())


def get_run(db: Session, run_id: str) -> WorkflowRun:
    obj = db.scalar(select(WorkflowRun).where(WorkflowRun.run_id == run_id))
    if not obj:
        raise ErrNotFound(f"运行记录 {run_id} 不存在")
    return obj


def _is_reachable(nid: str, entry: str, edges: list[dict], outputs: dict) -> bool:
    """判断节点在当前执行上下文中是否可达(BFS + 条件边过滤)"""
    if nid == entry:
        return True
    # 反向 BFS, 从 nid 往回走, 至少有一条入边且其 source 已被执行且条件满足
    in_edges = [e for e in edges if e.get("target") == nid]
    if not in_edges:
        return False
    for e in in_edges:
        src = e.get("source")
        if src not in outputs:
            continue
        cond = e.get("condition")
        if not cond:
            return True
        src_out = outputs.get(src) or {}
        result = src_out.get("condition_result")
        # condition 边: truthy/falsy 或 key=value
        if cond in ("true", "yes", "truthy"):
            if result:
                return True
        elif cond in ("false", "no", "falsy"):
            if not result:
                return True
        else:
            # cond = "xxx=yyy" 或 cond 值等于 src_out.value
            if str(result) == str(cond):
                return True
    return False


def run_workflow_async(wf_id: int, body: WorkflowRunIn, user_id: int = 0) -> dict:
    """异步执行工作流：立即返回 run_id，后台执行工作流"""
    from app.db.session import SessionLocal
    from app.core.scheduler import start_scheduler
    
    db = SessionLocal()
    try:
        wf = get_workflow(db, wf_id)
        if not wf.enabled:
            raise ErrBadRequest(f"工作流 '{wf.name}' 已禁用")
        
        run_id = uuid.uuid4().hex[:12]
        
        # 创建初始运行记录
        run_rec = WorkflowRun(
            run_id=run_id, workflow_id=wf.id, workflow_name=wf.name, user_id=user_id,
            status="running", input_data=body.input or body.variables or {}, logs=[f"🚀 工作流 {wf.name} (run_id={run_id}) 开始执行"],
        )
        db.add(run_rec)
        db.commit()
        db.refresh(run_rec)
    finally:
        db.close()
    
    # 使用 scheduler 立即执行
    scheduler = start_scheduler()
    
    def _run_async_task():
        """后台执行工作流的实际任务"""
        db = SessionLocal()
        try:
            result = run_workflow(db, wf_id, body, user_id)
            _workflow_results[run_id] = result
        except Exception as e:
            logger.exception(f"异步工作流执行失败: {e}")
            _workflow_results[run_id] = {"run_id": run_id, "status": "failed", "error": str(e)}
        finally:
            db.close()
    
    # 使用 date trigger 立即执行（run_date=None 表示立即执行）
    scheduler.add_job(
        _run_async_task,
        trigger="date",
        run_date=None,
        id=f"workflow_run_{run_id}",
        replace_existing=True,
        misfire_grace_time=30,
    )
    
    return {
        "run_id": run_id,
        "status": "running",
        "message": "工作流已提交，正在后台执行",
    }
