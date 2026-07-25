"""ORM Mixin: 审计字段
- created_by: 创建者 user_id
- created_at / updated_at: 时间戳(模型已各自有,这里提供统一基类)
删除逻辑复用现有 enabled 字段(enabled=False 视为已删除,查询层过滤)
"""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now, utc_now_naive


class CreatedByMixin:
    """创建者审计字段"""
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True,
                                                    comment="创建者 user_id")


class TimestampMixin:
    """时间戳"""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive,
                                                  onupdate=utc_now_naive, nullable=False)
