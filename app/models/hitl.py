"""
HITL (Human-In-The-Loop) 待确认任务模型

高危工具（delete_workflow、host_shell、save_as_skill 等）不直接执行，而是生成一条 pending_confirmation
记录，返回给前端。前端弹窗让用户确认/拒绝后，调用 /api/v1/hitl/{id}/confirm 或 /deny。
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, BigInteger, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.types import pk_column
from app.core.time import utc_now_naive


class PendingConfirmation(Base):
    """待用户确认的操作"""
    __tablename__ = "pending_confirmations"

    id: Mapped[int] = pk_column()
    # 关联用户/会话/工具
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    tool_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # 工具调用参数（确认后重放用）
    args_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 展示给用户看的摘要（中文说明）
    summary: Mapped[str] = mapped_column(Text, default="")
    # 风险等级：low/medium/high/critical
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    # 状态：pending/confirmed/denied/expired
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")
    # 确认/拒绝时的备注
    decision_note: Mapped[str] = mapped_column(Text, default="")
    # 执行结果（confirmed 后填入）
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 过期时间
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
