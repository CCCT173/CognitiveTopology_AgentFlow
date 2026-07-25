"""会话/消息历史请求响应"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ThreadOut(BaseModel):
    id: int
    thread_id: str
    agent_name: str
    title: str
    last_message: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ThreadRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}
