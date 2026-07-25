"""Workflow API Key - 外部调用凭据

每个工作流可生成多个 API Key，外部脚本通过
POST /api/v1/execute/wf_{key} 带 inputs 调用工作流。

api_key 存 SHA256 哈希（和 refresh_token 一致），
创建时返回明文 key 一次。
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BigInteger, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.types import pk_column
from app.core.time import utc_now_naive


def generate_wf_key() -> str:
    """生成明文 key"""
    return f"wf_{secrets.token_urlsafe(24).replace('-', 'a').replace('_', 'b')}"[:36]


def hash_wf_key(plain_key: str) -> str:
    """SHA256 哈希存储"""
    return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()


class WorkflowApiKey(Base):
    __tablename__ = "workflow_api_keys"
    __table_args__ = (
        UniqueConstraint("workflow_id", "name", name="uq_wf_key_name"),
        Index("ix_wf_key_key", "api_key"),
    )

    id: Mapped[int] = pk_column()
    workflow_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="default")
    # SHA256 哈希存储
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 仅在内存中保留明文，不持久化
    api_key: Mapped[str] = mapped_column(String(64), default="", nullable=True)
    # 启用状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 过期时间（空=永不过期）
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 调用统计
    calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_ip: Mapped[str] = mapped_column(String(64), default="")
    created_by: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
