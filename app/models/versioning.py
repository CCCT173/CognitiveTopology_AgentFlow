"""
版本快照模型:
- activity_log: 记录 Agent/Workflow 的每次重要变更（创建/修改/运行）
- workflow_versions/agent_versions: 每次 publish 时的快照
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now_naive


class ActivityLog(Base):
    """审计/活动日志: agent/workflow 每次操作的记录"""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    # agent/workflow/skill/kb/user
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True)
    # create/update/delete/run/publish/rollback/login
    action: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0, index=True)
    # 变更前/后的摘要 JSON
    before_json: Mapped[str] = mapped_column(Text, default="")
    after_json: Mapped[str] = mapped_column(Text, default="")
    # 元数据（IP、UA、客户端）
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False, index=True)


class WorkflowVersion(Base):
    """工作流版本快照（publish 时写入）"""
    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                              ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    # 完整 DSL 快照
    definition_json: Mapped[str] = mapped_column(Text)
    changelog: Mapped[str] = mapped_column(Text, default="")
    published_by: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    created_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class AgentVersion(Base):
    """Agent 版本快照"""
    __tablename__ = "agent_versions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                          ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    # 完整 agent 配置快照
    config_json: Mapped[str] = mapped_column(Text)
    changelog: Mapped[str] = mapped_column(Text, default="")
    published_by: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    created_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
