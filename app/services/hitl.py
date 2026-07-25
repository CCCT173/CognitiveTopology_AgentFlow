"""
HITL (Human-In-The-Loop) 服务

- create_confirmation: 工具调用前生成待确认记录
- confirm: 用户确认后真正执行工具
- deny: 用户拒绝
- list_pending: 列出用户待处理确认

高危工具（requires_confirmation=True）的 run() 方法不直接执行，而是返回 ToolResult(requires_confirmation=True)
并带 confirmation_id。上游 MetaRunner 检测到这个标志时把 confirmation_id 返回给前端，等用户决定。
"""
from __future__ import annotations
import json
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.models.hitl import PendingConfirmation
from app.core.time import utc_now_naive
from app.tools import get_registry, ToolResult


DEFAULT_TTL_MIN = 30  # 待确认默认 30 分钟过期


def create_confirmation(
    db: Session,
    *,
    user_id: int,
    tool_name: str,
    args: dict,
    summary: str,
    risk_level: str = "medium",
    thread_id: str = "",
    ttl_min: int = DEFAULT_TTL_MIN,
) -> PendingConfirmation:
    """创建一条待确认记录"""
    pc = PendingConfirmation(
        user_id=user_id,
        thread_id=thread_id,
        tool_name=tool_name,
        args_json=args or {},
        summary=summary,
        risk_level=risk_level,
        expires_at=utc_now_naive() + timedelta(minutes=ttl_min),
    )
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return pc


def _get_pending(db: Session, cid: int, user_id: int) -> PendingConfirmation | None:
    return db.scalar(
        select(PendingConfirmation).where(
            PendingConfirmation.id == cid,
            PendingConfirmation.user_id == user_id,
            PendingConfirmation.status == "pending",
        )
    )


def confirm(db: Session, confirmation_id: int, user_id: int, note: str = "") -> dict:
    """确认执行：真正调用工具"""
    pc = _get_pending(db, confirmation_id, user_id)
    if not pc:
        return {"ok": False, "error": "待确认记录不存在或已处理"}
    # 检查过期
    if pc.expires_at and pc.expires_at < utc_now_naive():
        pc.status = "expired"
        pc.decided_at = utc_now_naive()
        db.commit()
        return {"ok": False, "error": "已过期，请重新发起操作"}

    # 从注册表取工具并重放
    registry = get_registry()
    tool = registry.get(pc.tool_name)
    if not tool:
        pc.status = "denied"
        pc.decision_note = f"工具 {pc.tool_name} 已不存在"
        pc.decided_at = utc_now_naive()
        db.commit()
        return {"ok": False, "error": f"工具 {pc.tool_name} 已卸载"}

    try:
        result = tool.run(ctx=None, **pc.args_json)
        if isinstance(result, ToolResult):
            result_dict = {"ok": result.ok, "output": result.output, "error": result.error, "data": result.data}
        else:
            result_dict = {"ok": True, "output": str(result), "data": result}
    except Exception as e:
        result_dict = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    pc.status = "confirmed"
    pc.decision_note = note
    pc.result_json = result_dict
    pc.decided_at = utc_now_naive()
    db.commit()
    return {"ok": True, "confirmation_id": confirmation_id, "result": result_dict}


def deny(db: Session, confirmation_id: int, user_id: int, reason: str = "") -> dict:
    """用户拒绝"""
    pc = _get_pending(db, confirmation_id, user_id)
    if not pc:
        return {"ok": False, "error": "待确认记录不存在或已处理"}
    pc.status = "denied"
    pc.decision_note = reason or "用户拒绝"
    pc.decided_at = utc_now_naive()
    db.commit()
    return {"ok": True, "confirmation_id": confirmation_id, "status": "denied"}


def list_pending(db: Session, user_id: int, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(PendingConfirmation)
        .where(PendingConfirmation.user_id == user_id, PendingConfirmation.status == "pending")
        .order_by(PendingConfirmation.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "tool_name": r.tool_name,
            "summary": r.summary,
            "risk_level": r.risk_level,
            "args": r.args_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
        for r in rows
    ]


def expire_old(db: Session) -> int:
    """把过期的 pending 标记为 expired（定时任务用）"""
    now = utc_now_naive()
    rows = db.scalars(
        select(PendingConfirmation).where(
            PendingConfirmation.status == "pending",
            PendingConfirmation.expires_at.is_not(None),
            PendingConfirmation.expires_at < now,
        )
    ).all()
    for r in rows:
        r.status = "expired"
    db.commit()
    return len(rows)
