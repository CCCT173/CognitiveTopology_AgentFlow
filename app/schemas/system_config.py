"""系统配置 Pydantic schema"""
from pydantic import BaseModel, Field


class AIConfigOut(BaseModel):
    """返回给前端的 AI 配置（敏感字段脱敏）"""
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: str = ""
    max_tokens: str = ""
    embedding_provider: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""


class AIConfigUpdate(BaseModel):
    """前端提交的更新（只传需要改的字段）"""
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_temperature: str | None = None
    ai_max_tokens: str | None = None
    embedding_provider: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
