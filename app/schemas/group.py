"""群组相关请求/响应"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    member_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class GroupMemberOut(BaseModel):
    user_id: int
    username: str
    avatar_url: str
    role: str
    online: bool = False
    last_active_at: datetime


class GroupAgentOut(BaseModel):
    agent_id: int
    name: str
    description: str
    shared_by: int


class GroupKBOut(BaseModel):
    kb_id: int
    name: str
    description: str
    shared_by: int


class GroupMessageIn(BaseModel):
    content: str = Field(..., min_length=1)
    agent_name: Optional[str] = Field(None, description="调用群内共享agent,不传则普通消息")
    reply_to: Optional[int] = None


class GroupMessageOut(BaseModel):
    id: int
    group_id: int
    user_id: int
    username: str = ""
    avatar_url: str = ""
    agent_id: Optional[int] = None
    content: str
    reply_to: Optional[int] = None
    bot: bool = False
    created_at: datetime


class GroupNoticeIn(BaseModel):
    title: str = Field("", max_length=128)
    content: str = Field(..., min_length=1)
    pinned: bool = False


class GroupNoticeOut(BaseModel):
    id: int
    group_id: int
    author_id: int
    author_name: str = ""
    author_avatar: str = ""
    title: str
    content: str
    pinned: bool
    created_at: datetime
    updated_at: datetime
    read_count: int = 0
    is_read: bool = False
