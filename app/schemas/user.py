"""用户 请求/响应模型"""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class RegisterIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    account: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=6, max_length=64)
    bind_admin_id: int | None = Field(None, description="绑定的次级管理员 user_id, 普通用户必填")


class LoginIn(BaseModel):
    account: str   # 账号或邮箱
    password: str


class UserUpdateMe(BaseModel):
    """当前登录用户修改自己资料"""
    username: Optional[str] = Field(None, max_length=64)
    email: Optional[str] = Field(None, max_length=128)
    avatar_url: Optional[str] = None
    old_password: Optional[str] = None   # 改密码时必填旧密码
    new_password: Optional[str] = Field(None, min_length=6, max_length=64)
    # 个人资料扩展
    title: Optional[str] = Field(None, max_length=64)
    company: Optional[str] = Field(None, max_length=128)
    department: Optional[str] = Field(None, max_length=64)
    location: Optional[str] = Field(None, max_length=64)
    phone: Optional[str] = Field(None, max_length=32)
    website: Optional[str] = Field(None, max_length=256)
    bio: Optional[str] = None
    birthday: Optional[date] = None


class UserOut(BaseModel):
    user_id: int
    username: str
    account: str
    email: str
    avatar_url: str
    role: str
    bind_admin_id: int | None = None
    manager_id: int | None = None
    enabled: bool
    created_at: datetime
    # 个人资料扩展
    title: str = ""
    company: str = ""
    department: str = ""
    location: str = ""
    phone: str = ""
    website: str = ""
    bio: str = ""
    birthday: Optional[date] = None
    last_active_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class UserTreeNode(UserOut):
    """组织树节点: 带 children 递归"""
    children: list["UserTreeNode"] = []


class UserCreate(BaseModel):
    """管理员创建用户"""
    username: str = Field(..., min_length=1, max_length=64)
    account: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=6, max_length=64)
    role: str = Field("user", pattern="^(admin|user)$")
    manager_id: int | None = None
    department: str = ""
    title: str = ""


class UserUpdate(BaseModel):
    """管理员修改用户"""
    username: Optional[str] = Field(None, max_length=64)
    email: Optional[str] = Field(None, max_length=128)
    role: Optional[str] = Field(None, pattern="^(admin|user)$")
    manager_id: Optional[int] = None  # 传 None = 置空
    department: Optional[str] = None
    title: Optional[str] = None
    enabled: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=64)


UserTreeNode.model_rebuild()


class UserOnlineOut(UserOut):
    """列表里显示在线状态"""
    online: bool = False
    last_active_at: datetime


class LoginOut(BaseModel):
    token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 900   # access token 有效期 15 分钟（秒）
    user: UserOut
