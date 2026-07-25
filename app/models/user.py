"""用户表"""
from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, BigInteger, Integer, Text, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now, utc_now_naive


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), comment="用户名(昵称)")
    account: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录账号")
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="邮箱")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希(bcrypt)")
    avatar_url: Mapped[str] = mapped_column(String(512), default="", comment="头像URL")
    role: Mapped[str] = mapped_column(String(16), default="user",
                                       comment="角色: super_admin/admin/user")
    # 个人资料扩展
    title: Mapped[str] = mapped_column(String(64), default="", comment="职位/头衔")
    company: Mapped[str] = mapped_column(String(128), default="", comment="公司/组织")
    department: Mapped[str] = mapped_column(String(64), default="", comment="所属部门")
    location: Mapped[str] = mapped_column(String(64), default="", comment="所在地")
    phone: Mapped[str] = mapped_column(String(32), default="", comment="联系电话")
    website: Mapped[str] = mapped_column(String(256), default="", comment="个人主页链接")
    bio: Mapped[str] = mapped_column(Text, default="", comment="个人简介")
    birthday: Mapped[date | None] = mapped_column(Date, default=None, nullable=True, comment="生日")
    # 组织树: manager_id 是直属上级 user_id (自引用 FK); super_admin 的 manager_id 为 NULL
    manager_id: Mapped[int | None] = mapped_column(BigInteger, default=None, nullable=True, index=True,
                                                    comment="直属上级用户ID")
    # 普通用户绑定的次级管理员 user_id; admin/super_admin 自身为 NULL
    bind_admin_id: Mapped[int | None] = mapped_column(BigInteger, default=None, nullable=True, index=True,
                                                       comment="绑定的次级管理员ID, 普通用户必填")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活(封禁)")
    # 在线状态通过 last_active_at 推断: utcnow - last_active_at < 60s 视为在线
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
