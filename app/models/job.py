"""
后台任务模型：
- jobs 表记录异步任务状态（pending/running/done/failed/lost）
- 启动时孤儿任务（running 超过 N 分钟）标记为 lost 并重入队
- 提供 enqueue() / update_status() 接口
"""
from __future__ import annotations
from typing import Any, Optional
import json
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now_naive


class Job(Base):
    """后台任务"""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True, comment="任务名")
    params_json: Mapped[str] = mapped_column(Text, default="{}", comment="参数JSON")
    # pending/running/done/failed/lost
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    result_json: Mapped[str] = mapped_column(Text, default="", nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="worker标识")
    heartbeat_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    started_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    @property
    def params(self) -> dict:
        try:
            return json.loads(self.params_json or "{}")
        except Exception:
            return {}

    @property
    def result(self) -> Any:
        if not self.result_json:
            return None
        try:
            return json.loads(self.result_json)
        except Exception:
            return None
