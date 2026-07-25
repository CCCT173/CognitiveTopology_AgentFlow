"""Refresh Token 模型 - 用于 JWT 无感刷新

access token 短有效期（15min），refresh token 长有效期（7天）存 DB。
refresh 一次后旧 refresh token 轮换（rotation），防止重放。
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.types import pk_column
from app.core.time import utc_now_naive


class RefreshToken(Base):
    """refresh_tokens 表"""
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = pk_column()
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # token 哈希（不存明文）
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    # 设备/IP 信息
    device: Mapped[str] = mapped_column(String(200), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    # 过期时间
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 是否已被使用（轮换后作废）
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 是否已被撤销（logout）
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 替换它的下一个 token（轮换链）
    replaced_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
