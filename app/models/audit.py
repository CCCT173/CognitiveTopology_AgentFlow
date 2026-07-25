"""系统监控 + 操作日志模型"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class AuditLog(Base):
    """操作审计日志"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64), index=True)          # create/update/delete/login/...
    resource: Mapped[str] = mapped_column(String(64), index=True)        # agent/workflow/skill/...
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(16), default="success")   # success/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index("ix_audit_logs_created_action", "created_at", "action"),
    )
