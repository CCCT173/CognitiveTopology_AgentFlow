"""工作流共享权限

支持用户级和用户组级授权：
- viewer：可查看、可运行
- editor：可编辑、可发布
- owner：完整控制（授权/删除）

创建者自动拥有 owner 权限；super_admin 有全部权限。
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger, Integer, UniqueConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.types import pk_column
from app.core.time import utc_now_naive


class WorkflowPermission(Base):
    __tablename__ = "workflow_permissions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "user_id", name="uq_wf_perm_user"),
        Index("ix_wf_perm_user", "user_id", "role"),
    )

    id: Mapped[int] = pk_column()
    workflow_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # viewer / editor / owner
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    granted_by: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


# 常量
ROLE_VIEWER = "viewer"
ROLE_EDITOR = "editor"
ROLE_OWNER = "owner"

ROLE_LEVELS = {ROLE_VIEWER: 1, ROLE_EDITOR: 2, ROLE_OWNER: 3}


def role_at_least(role: str, required: str) -> bool:
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(required, 0)
