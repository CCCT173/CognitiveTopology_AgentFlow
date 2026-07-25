"""系统配置服务 — DB 存储 + 内存缓存 + 脱敏"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.logger import logger
from app.models.system_config import SystemConfig
from app.core.time import utc_now

# -------- 模块级缓存 --------
_cached: dict[str, str] = {}
_loaded: bool = False
# 缓存的原始值（用于 LLM 服务读取，不做脱敏）
_raw_cache: dict[str, str] = {}

MASK_CHAR = "●"
MASK_KEEP = 4   # 敏感字段保留前 N 个字符


def _mask(value: str) -> str:
    """对敏感值脱敏：前 4 位明文，其余用 ● 替代"""
    if len(value) <= MASK_KEEP * 2:
        return value[:MASK_KEEP] + MASK_CHAR * max(len(value) - MASK_KEEP, 0)
    return value[:MASK_KEEP] + MASK_CHAR * (len(value) - MASK_KEEP * 2) + value[-MASK_KEEP:]


def _is_sensitive(key: str) -> bool:
    return key in SystemConfig.SENSITIVE_KEYS


def load_config(db: Session) -> dict[str, str]:
    """从 DB 加载所有配置并更新缓存"""
    global _loaded, _cached, _raw_cache
    rows = db.execute(select(SystemConfig)).scalars().all()
    _raw_cache = {r.key: r.value for r in rows if r.value}
    _cached = {
        k: _mask(v) if _is_sensitive(k) else v
        for k, v in _raw_cache.items()
    }
    _loaded = True
    logger.info(f"SystemConfig loaded: {len(_raw_cache)} keys")
    return _cached


def get_config(key: str | None = None, default: str = "") -> str | dict[str, str]:
    """读取配置（从缓存）。不传 key 返回全部（脱敏版）"""
    if not _loaded:
        return default if key else {}
    if key:
        return _cached.get(key, default)
    return dict(_cached)


def get_raw(key: str, default: str = "") -> str:
    """读取原始值（不脱敏，供 LLM 服务内部使用）"""
    if not _loaded:
        return default
    return _raw_cache.get(key, default)


def set_configs(db: Session, updates: dict[str, str], updated_by: int) -> dict[str, str]:
    """批量 upsert 配置，更新缓存，返回脱敏后的全部配置"""
    global _cached, _raw_cache
    now = utc_now()
    for key, value in updates.items():
        if key not in SystemConfig.KEYS:
            continue
        existing = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if existing:
            existing.value = value
            existing.updated_at = now
            existing.updated_by = updated_by
        else:
            db.add(SystemConfig(
                key=key, value=value,
                description=SystemConfig.KEYS.get(key, ""),
                updated_at=now, updated_by=updated_by,
            ))
    db.commit()
    # 清除 LLM 客户端缓存，使新配置生效
    try:
        from app.services.llm import clear_llm_cache
        clear_llm_cache()
    except Exception:
        pass
    # 重载缓存
    load_config(db)
    return dict(_cached)


def ensure_loaded(db: Session):
    """确保配置已加载（懒加载入口，首次调用 get_chat_model 时触发）"""
    global _loaded
    if not _loaded:
        load_config(db)


def get_llm_config() -> dict[str, str]:
    """获取 LLM 服务层需要的配置（原始值，不回退 .env 在此做）"""
    return {
        "provider": get_raw("ai_provider", ""),
        "api_key": get_raw("ai_api_key", ""),
        "base_url": get_raw("ai_base_url", ""),
        "model": get_raw("ai_model", ""),
        "temperature": get_raw("ai_temperature", ""),
        "max_tokens": get_raw("ai_max_tokens", ""),
    }


def get_embedding_config() -> dict[str, str]:
    return {
        "provider": get_raw("embedding_provider", ""),
        "api_key": get_raw("embedding_api_key", ""),
        "base_url": get_raw("embedding_base_url", ""),
        "model": get_raw("embedding_model", ""),
    }


def test_llm_connection(config: dict[str, str]) -> dict:
    """测试 AI API 连通性"""
    from langchain_core.messages import HumanMessage
    from app.services.llm import get_chat_model
    provider = config.get("provider", "")
    model = config.get("model", "")
    try:
        m = get_chat_model(provider=provider, model=model, temperature=0.1, force_db_config=config)
        resp = m.invoke([HumanMessage(content="hi")], max_tokens=10)
        return {"ok": True, "reply": str(getattr(resp, "content", ""))[:50], "provider": provider, "model": model}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "provider": provider, "model": model}
