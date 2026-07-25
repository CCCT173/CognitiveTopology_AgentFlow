"""群组 ORM 模型"""
from datetime import datetime
from sqlalchemy import String, BigInteger, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.core.time import utc_now, utc_now_naive


class Group(Base):
    __tablename__ = "work_groups"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    members: Mapped[list["GroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    group: Mapped[Group] = relationship(back_populates="members")


class GroupAgent(Base):
    __tablename__ = "group_agents"

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    shared_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class GroupKB(Base):
    __tablename__ = "group_kbs"

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), primary_key=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True)
    shared_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class GroupWorkflow(Base):
    __tablename__ = "group_workflows"

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), primary_key=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True)
    shared_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class GroupSkill(Base):
    __tablename__ = "group_skills"

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    shared_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class GroupMessage(Base):
    """群组内聊天消息。
    - 普通消息: agent_id 为空, 由 user_id 发送
    - Agent 回复: agent_id 指向群内共享的 agent, user_id 为触发者, bot=True
    """
    __tablename__ = "group_messages"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    reply_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="引用消息id")
    bot: Mapped[bool] = mapped_column(default=False, comment="True=agent自动回复")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False, index=True)


class GroupNotice(Base):
    """群组公告/通知。owner/admin 可发布，置顶排序优先，成员可标记已读。"""
    __tablename__ = "group_notices"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_groups.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class GroupNoticeRead(Base):
    """公告已读记录"""
    __tablename__ = "group_notice_reads"

    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("group_notices.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
