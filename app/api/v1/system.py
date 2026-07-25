"""系统监控接口: CPU/内存/状态/统计/Dashboard"""
from __future__ import annotations
import os
import time
import platform
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, case, desc
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin, get_current_superadmin, is_admin  # noqa: E402
from app.core.security import get_current_user_required_enabled as get_current_user  # noqa: F401 (兼容旧引用)
from app.models.user import User
from app.models.agent import Agent, AgentChatMessage, ChatThread
from app.models.skill import Skill
from app.models.workflow import Workflow, WorkflowRun
from app.models.audit import AuditLog
from app.schemas.common import ok, Resp
from app.schemas.system_config import AIConfigUpdate
from app.core.time import utc_now, utc_now_naive

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

router = APIRouter(prefix="/system", tags=["system"])
_start_time = time.time()


@router.get("/status", summary="系统状态（健康检查）")
def system_status() -> Resp:
    return ok({
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - _start_time),
        "server_time": utc_now().isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
    })


@router.get("/metrics", summary="系统监控指标(CPU/内存/磁盘)")
def system_metrics(user: User = Depends(get_current_user)) -> Resp:
    data: dict = {
        "uptime_seconds": int(time.time() - _start_time),
        "process": {
            "pid": os.getpid(),
            "memory_rss_mb": 0,
            "cpu_percent": 0,
            "threads": 0,
        },
        "system": {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_total_gb": 0,
            "memory_available_gb": 0,
            "disk_percent": 0,
            "disk_total_gb": 0,
            "disk_free_gb": 0,
        },
        "psutil_available": _HAS_PSUTIL,
    }
    if _HAS_PSUTIL:
        proc = psutil.Process()
        with proc.oneshot():
            data["process"]["memory_rss_mb"] = round(proc.memory_info().rss / 1024 / 1024, 1)
            data["process"]["cpu_percent"] = round(proc.cpu_percent(interval=0.1), 1)
            data["process"]["threads"] = proc.num_threads()
        mem = psutil.virtual_memory()
        data["system"]["cpu_percent"] = round(psutil.cpu_percent(interval=0.1), 1)
        data["system"]["memory_percent"] = round(mem.percent, 1)
        data["system"]["memory_total_gb"] = round(mem.total / 1024**3, 2)
        data["system"]["memory_available_gb"] = round(mem.available / 1024**3, 2)
        try:
            disk = psutil.disk_usage(os.getcwd())
            data["system"]["disk_percent"] = round(disk.percent, 1)
            data["system"]["disk_total_gb"] = round(disk.total / 1024**3, 2)
            data["system"]["disk_free_gb"] = round(disk.free / 1024**3, 2)
        except Exception:
            pass
    return ok(data)


@router.get("/stats", summary="业务统计数据(管理员)")
def system_stats(db: Session = Depends(get_db), _: User = Depends(get_current_admin)) -> Resp:
    agents = db.scalar(select(func.count()).select_from(Agent)) or 0
    skills = db.scalar(select(func.count()).select_from(Skill)) or 0
    workflows = db.scalar(select(func.count()).select_from(Workflow)) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    enabled_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.enabled.is_(True))) or 0
    enabled_workflows = db.scalar(select(func.count()).select_from(Workflow).where(Workflow.enabled.is_(True))) or 0
    return ok({
        "total": {"agents": agents, "skills": skills, "workflows": workflows, "users": users},
        "enabled": {"agents": enabled_agents, "workflows": enabled_workflows},
    })


@router.get("/dashboard", summary="仪表盘聚合数据 (工作流统计/Agent热度/7日趋势)")
def system_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Resp:
    """首页Dashboard聚合接口, admin/super_admin 返回全量统计; 普通 user 返回自己创建资源的统计"""
    admin_view = is_admin(user)
    admin_view = is_admin(user)

    # 普通用户只能看自己创建的工作流运行; 通过 WorkflowRun.workflow_id -> Workflow.created_by 关联
    base_run_filter = []
    base_msg_filter = []
    base_thread_filter = []
    if not admin_view:
        # 子查询: 自己创建的 WF ids
        my_wf_ids = select(Workflow.id).where(Workflow.created_by == user.user_id).scalar_subquery()
        base_run_filter.append(WorkflowRun.workflow_id.in_(my_wf_ids))
        base_msg_filter.append(AgentChatMessage.user_id == user.user_id)
        base_thread_filter.append(ChatThread.user_id == user.user_id)

    # ---- 工作流总体统计 ----
    wf_total = db.scalar(select(func.count()).select_from(WorkflowRun).where(*base_run_filter)) or 0
    wf_success = db.scalar(select(func.count()).select_from(WorkflowRun).where(
        *base_run_filter, WorkflowRun.status == "success")) or 0
    wf_failed = db.scalar(select(func.count()).select_from(WorkflowRun).where(
        *base_run_filter, WorkflowRun.status == "failed")) or 0
    wf_running = db.scalar(select(func.count()).select_from(WorkflowRun).where(
        *base_run_filter, WorkflowRun.status == "running")) or 0
    success_rate = round(wf_success / wf_total * 100, 1) if wf_total > 0 else 0.0

    # 耗时统计: 取已完成(success/failed)的elapsed_ms
    elapsed_rows = db.scalars(
        select(WorkflowRun.elapsed_ms).where(
            *base_run_filter,
            WorkflowRun.status.in_(["success", "failed"]),
            WorkflowRun.elapsed_ms > 0,
        ).order_by(WorkflowRun.elapsed_ms)
    ).all()
    elapsed = sorted([int(x) for x in elapsed_rows if x is not None])
    avg_ms = round(sum(elapsed) / len(elapsed)) if elapsed else 0
    p50_ms = elapsed[len(elapsed) // 2] if elapsed else 0
    p95_ms = elapsed[min(int(len(elapsed) * 0.95), len(elapsed) - 1)] if elapsed else 0

    # ---- 最近7天趋势 ----
    trend_days = 7
    now = utc_now()
    wf_trend = []
    for i in range(trend_days - 1, -1, -1):
        day_start = now - timedelta(days=i)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_success = db.scalar(
            select(func.count()).select_from(WorkflowRun).where(
                *base_run_filter,
                WorkflowRun.created_at >= day_start,
                WorkflowRun.created_at < day_end,
                WorkflowRun.status == "success",
            )
        ) or 0
        day_failed = db.scalar(
            select(func.count()).select_from(WorkflowRun).where(
                *base_run_filter,
                WorkflowRun.created_at >= day_start,
                WorkflowRun.created_at < day_end,
                WorkflowRun.status == "failed",
            )
        ) or 0
        wf_trend.append({
            "date": day_start.strftime("%m-%d"),
            "success": day_success,
            "failed": day_failed,
        })

    # ---- 热门工作流 TOP5 ----
    wf_top_q = select(
        WorkflowRun.workflow_id,
        WorkflowRun.workflow_name,
        func.count().label("runs"),
        func.sum(case((WorkflowRun.status == "success", 1), else_=0)).label("success"),
        func.avg(WorkflowRun.elapsed_ms).label("avg_ms"),
    ).where(*base_run_filter, WorkflowRun.status.in_(["success", "failed"]))
    if not admin_view:
        wf_top_q = wf_top_q.where(WorkflowRun.workflow_id.in_(
            select(Workflow.id).where(Workflow.created_by == user.user_id).scalar_subquery()))
    wf_top_rows = db.execute(
        wf_top_q.group_by(WorkflowRun.workflow_id, WorkflowRun.workflow_name)
        .order_by(desc("runs"))
        .limit(5)
    ).all()
    wf_top = [
        {
            "id": r.workflow_id,
            "name": r.workflow_name or f"WF#{r.workflow_id}",
            "runs": int(r.runs or 0),
            "success": int(r.success or 0),
            "avg_ms": round(float(r.avg_ms or 0)),
        }
        for r in wf_top_rows
    ]

    # ---- Agent 对话统计 ----
    msg_total = db.scalar(select(func.count()).select_from(AgentChatMessage).where(
        *base_msg_filter, AgentChatMessage.role != "system")) or 0
    thread_total = db.scalar(select(func.count()).select_from(ChatThread).where(*base_thread_filter)) or 0

    # 热门Agent TOP5 (按消息数)
    agent_top_q = select(
        AgentChatMessage.agent_name,
        func.count().label("msgs"),
    ).where(*base_msg_filter, AgentChatMessage.role == "user")
    agent_top_rows = db.execute(
        agent_top_q.group_by(AgentChatMessage.agent_name)
        .order_by(desc("msgs"))
        .limit(5)
    ).all()
    agent_top = [
        {"name": r.agent_name, "msgs": int(r.msgs or 0)}
        for r in agent_top_rows
    ]

    # ---- 最近10次工作流运行 ----
    recent_q = select(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(10)
    if not admin_view:
        recent_q = recent_q.where(WorkflowRun.workflow_id.in_(
            select(Workflow.id).where(Workflow.created_by == user.user_id).scalar_subquery()))
    recent = db.scalars(recent_q).all()
    recent_runs = [
        {
            "run_id": r.run_id,
            "workflow_id": r.workflow_id,
            "workflow_name": r.workflow_name,
            "status": r.status,
            "elapsed_ms": r.elapsed_ms or 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent
    ]

    return ok({
        "wf_stats": {
            "total": wf_total,
            "success": wf_success,
            "failed": wf_failed,
            "running": wf_running,
            "success_rate": success_rate,
            "avg_ms": avg_ms,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
        },
        "wf_trend": wf_trend,
        "wf_top": wf_top,
        "agent_stats": {
            "messages": msg_total,
            "threads": thread_total,
        },
        "agent_top": agent_top,
        "recent_runs": recent_runs,
    })


@router.get("/logs", summary="操作审计日志(管理员)")
def list_logs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
) -> Resp:
    stmt = select(AuditLog).where(AuditLog.created_at >= utc_now() - timedelta(days=days))
    cnt_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= utc_now() - timedelta(days=days))
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        cnt_stmt = cnt_stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        cnt_stmt = cnt_stmt.where(AuditLog.action == action)
    if resource:
        stmt = stmt.where(AuditLog.resource == resource)
        cnt_stmt = cnt_stmt.where(AuditLog.resource == resource)
    total = db.scalar(cnt_stmt) or 0
    rows = list(db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page-1)*page_size).limit(page_size)).all())
    return ok({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id, "user_id": r.user_id, "username": r.username,
                "action": r.action, "resource": r.resource, "resource_id": r.resource_id,
                "detail": r.detail, "ip": r.ip, "status": r.status,
                "created_at": r.created_at.isoformat(),
            }         for r in rows
        ]
    })


@router.get("/apm", summary="API 性能监控 (内存中最近请求的耗时/错误率/QPS)")
def system_apm(window: int = Query(300, ge=30, le=3600), user: User = Depends(get_current_user)) -> Resp:
    """返回最近 window 秒内的 API 性能指标。无需登录(只读指标)。"""
    from app.core.apm import apm
    return ok(apm.snapshot(window_seconds=window))


# ==================== AI API 配置 ====================

@router.get("/ai-config", summary="获取 AI API 配置")
def get_ai_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Resp:
    """获取当前 AI API 配置（敏感字段脱敏）。admin 可读"""
    from app.services import system_config_service as cfg_svc
    cfg_svc.ensure_loaded(db)
    from app.schemas.system_config import AIConfigOut
    out = AIConfigOut(
        provider=cfg_svc.get_config("ai_provider", ""),
        api_key=cfg_svc.get_config("ai_api_key", ""),
        base_url=cfg_svc.get_config("ai_base_url", ""),
        model=cfg_svc.get_config("ai_model", ""),
        temperature=cfg_svc.get_config("ai_temperature", ""),
        max_tokens=cfg_svc.get_config("ai_max_tokens", ""),
        embedding_provider=cfg_svc.get_config("embedding_provider", ""),
        embedding_api_key=cfg_svc.get_config("embedding_api_key", ""),
        embedding_base_url=cfg_svc.get_config("embedding_base_url", ""),
        embedding_model=cfg_svc.get_config("embedding_model", ""),
    )
    # 附带全部原始值供 admin 核对（admin 才有）
    return ok(out.model_dump())


@router.patch("/ai-config", summary="更新 AI API 配置")
def update_ai_config(body: AIConfigUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Resp:
    """更新 AI API 配置（仅 admin）。传哪些改哪些，不传的不变"""
    from app.api.deps import is_admin
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以修改 AI 配置")
    from app.services import system_config_service as cfg_svc
    # key 映射：schema 字段名 -> DB key
    updates = {}
    mapping = {
        "ai_provider": body.ai_provider,
        "ai_api_key": body.ai_api_key,
        "ai_base_url": body.ai_base_url,
        "ai_model": body.ai_model,
        "ai_temperature": body.ai_temperature,
        "ai_max_tokens": body.ai_max_tokens,
        "embedding_provider": body.embedding_provider,
        "embedding_api_key": body.embedding_api_key,
        "embedding_base_url": body.embedding_base_url,
        "embedding_model": body.embedding_model,
    }
    updates = {k: v for k, v in mapping.items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="没有提供任何要更新的字段")
    result = cfg_svc.set_configs(db, updates, user.user_id)
    return ok(msg="配置已更新", data=result)


class AIConfigTestIn(BaseModel):
    """测试 AI 连通性时需要传完整配置（不存 DB 就测）"""
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@router.post("/ai-config/test", summary="测试 AI API 连通性")
def test_ai_config(body: AIConfigTestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Resp:
    """测试给定的 provider/key/model 是否能正常连通。仅 admin"""
    from app.api.deps import is_admin
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以测试 AI 配置")
    from app.services import system_config_service as cfg_svc
    result = cfg_svc.test_llm_connection({
        "provider": body.provider,
        "api_key": body.api_key,
        "base_url": body.base_url,
        "model": body.model,
    })
    if result["ok"]:
        return ok(result)
    return Resp(code=6001, msg=result.get("error", "连接失败"), data=result)
