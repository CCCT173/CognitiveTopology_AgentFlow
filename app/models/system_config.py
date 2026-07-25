"""系统配置 ORM 模型 — 键值对存储运行时配置（AI API、embedding 等）"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime
from app.db.session import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True, nullable=False, comment="配置键")
    value = Column(Text, nullable=False, comment="配置值（敏感字段加密存储）")
    description = Column(String(256), nullable=True, comment="配置说明")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(BigInteger, nullable=True, comment="最后修改人 user_id")

    # 预定义键名
    KEYS = {
        "ai_provider": "AI provider (ark/giteeai/deepseek)",
        "ai_api_key": "AI API Key（敏感）",
        "ai_base_url": "AI API Base URL",
        "ai_model": "AI 对话模型",
        "ai_temperature": "AI 默认温度 0-2",
        "ai_max_tokens": "AI 最大输出 tokens",
        "embedding_provider": "Embedding provider",
        "embedding_api_key": "Embedding API Key（敏感）",
        "embedding_base_url": "Embedding Base URL",
        "embedding_model": "Embedding 模型名",
    }

    SENSITIVE_KEYS = {"ai_api_key", "embedding_api_key"}
