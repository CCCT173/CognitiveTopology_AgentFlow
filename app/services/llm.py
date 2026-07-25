"""
LLM 客户端统一封装
- get_chat_model(): 返回 langchain ChatOpenAI 实例 (旧接口,兼容)
- get_chat_model_native(): 返回 (openai_client, model_name),用于 function-calling 场景
- build_chat_kwargs(agent): 返回 (client, model, kwargs) 供 chat.completions.create 使用,
  kwargs 包含 temperature/top_p/max_tokens/presence_penalty/frequency_penalty/extra_body(thinking)
  等全部可配置参数,按 settings + agent.llm_config 合并。
- 内置 timeout=60s + 重试2次
"""
from functools import lru_cache
from openai import OpenAI
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logger import logger


# ---------- LLM 参数默认值 (贴近 OpenAI/ARK 官方默认值) ----------
LLM_DEFAULTS: dict = {
    "temperature": 1.0,          # OpenAI 默认 1.0
    "top_p": 1.0,                # 默认 1.0 (不做 nucleus 截断)
    "max_tokens": None,          # 不限制
    "presence_penalty": 0.0,     # -2.0 ~ 2.0
    "frequency_penalty": 0.0,    # -2.0 ~ 2.0
    "stream": True,              # 默认开启流式
    "thinking": True,            # 默认开启并展示思考内容(对支持 reasoning 的模型生效)
}


def _get_db_cfg(key: str, default: str = "") -> str:
    """从 DB system_config 读配置（已在 system_config_service 内部缓存，不开 DB）"""
    try:
        from app.services.system_config_service import get_raw
        return get_raw(key, default)
    except Exception:
        return default


@lru_cache(maxsize=4)
def _client_for(provider: str) -> OpenAI:
    """创建 OpenAI 客户端，优先用 DB 配置的 api_key/base_url，否则回退 .env"""
    if provider == "giteeai":
        api_key = _get_db_cfg("ai_api_key") or settings.GITEEAI_API_KEY
        base_url = _get_db_cfg("ai_base_url") or settings.GITEEAI_BASE_URL
        if not api_key:
            raise ValueError("GITEEAI_API_KEY 未配置（DB 和 .env 均无）")
        return OpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    if provider == "ark":
        api_key = _get_db_cfg("ai_api_key") or settings.ARK_API_KEY
        base_url = _get_db_cfg("ai_base_url") or settings.ARK_BASE_URL
        if not api_key:
            raise ValueError("ARK_API_KEY 未配置（DB 和 .env 均无）")
        return OpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    if provider == "deepseek":
        api_key = _get_db_cfg("ai_api_key") or settings.DEEPSEEK_API_KEY
        base_url = _get_db_cfg("ai_base_url") or "https://api.deepseek.com/v1"
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置（DB 和 .env 均无）")
        return OpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    raise ValueError(f"未知 LLM_PROVIDER: {provider}")


@lru_cache(maxsize=4)
def _async_client_for(provider: str) -> AsyncOpenAI:
    """创建异步 OpenAI 客户端，优先用 DB 配置的 api_key/base_url，否则回退 .env"""
    if provider == "giteeai":
        api_key = _get_db_cfg("ai_api_key") or settings.GITEEAI_API_KEY
        base_url = _get_db_cfg("ai_base_url") or settings.GITEEAI_BASE_URL
        if not api_key:
            raise ValueError("GITEEAI_API_KEY 未配置（DB 和 .env 均无）")
        return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    if provider == "ark":
        api_key = _get_db_cfg("ai_api_key") or settings.ARK_API_KEY
        base_url = _get_db_cfg("ai_base_url") or settings.ARK_BASE_URL
        if not api_key:
            raise ValueError("ARK_API_KEY 未配置（DB 和 .env 均无）")
        return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    if provider == "deepseek":
        api_key = _get_db_cfg("ai_api_key") or settings.DEEPSEEK_API_KEY
        base_url = _get_db_cfg("ai_base_url") or "https://api.deepseek.com/v1"
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置（DB 和 .env 均无）")
        return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=2)
    raise ValueError(f"未知 LLM_PROVIDER: {provider}")


def _resolve_provider_model(agent=None) -> tuple[str, str, dict]:
    """根据 agent.llm_config + DB 配置 + settings 推断 (provider, model, 完整kwargs)

    优先级：agent.llm_config > DB system_config > .env settings
    """
    # 尝试从 DB 配置拿默认值
    try:
        from app.services.system_config_service import get_raw
    except Exception:
        get_raw = lambda k, d="": d

    provider = (get_raw("ai_provider") or settings.LLM_PROVIDER)
    cfg: dict = {}
    if agent is not None:
        cfg = dict(getattr(agent, "llm_config", None) or {})
        if cfg.get("provider"):
            provider = cfg["provider"]

    model = cfg.get("model") or (get_raw("ai_model") or "") or {
        "giteeai": settings.GITEEAI_CHAT_MODEL,
        "ark": settings.ARK_CHAT_MODEL,
        "deepseek": settings.DEEPSEEK_MODEL,
    }.get(provider, settings.GITEEAI_CHAT_MODEL)

    # 合并默认值: LLM_DEFAULTS < cfg
    kwargs: dict = {}
    for k, default in LLM_DEFAULTS.items():
        v = cfg.get(k, default)
        if v is None:
            continue
        kwargs[k] = v

    # thinking 映射到 ARK/GiteeAI 的 extra_body.thinking
    thinking = kwargs.pop("thinking", False)
    extra_body = dict(cfg.get("extra_body") or {})
    if thinking:
        extra_body.setdefault("thinking", {"type": "enabled"})
    if extra_body:
        kwargs["extra_body"] = extra_body

    return provider, model, kwargs


def _build_chat_client(agent=None) -> tuple[OpenAI, str]:
    """(兼容旧调用)返回原生 OpenAI 客户端 + model 名"""
    provider, model, _ = _resolve_provider_model(agent)
    return _client_for(provider), model


def build_chat_kwargs(agent=None) -> tuple[OpenAI, str, dict]:
    """返回 (client, model, create_kwargs)。
    create_kwargs 不包含 messages/tools,仅包含采样/长度/流式/thinking 等调用级参数。
    """
    provider, model, kwargs = _resolve_provider_model(agent)
    return _client_for(provider), model, kwargs


def build_chat_kwargs_async(agent=None) -> tuple[AsyncOpenAI, str, dict]:
    """返回异步 (client, model, create_kwargs)。
    create_kwargs 不包含 messages/tools,仅包含采样/长度/流式/thinking 等调用级参数。
    """
    provider, model, kwargs = _resolve_provider_model(agent)
    return _async_client_for(provider), model, kwargs


def get_chat_model(provider: str | None = None, model: str | None = None, temperature: float = 0.3,
                   force_db_config: dict | None = None) -> ChatOpenAI:
    """返回 langchain ChatOpenAI 实例。

    优先级：force_db_config（测试用）> DB system_config > .env settings
    """
    p = (provider or _get_db_cfg("ai_provider") or settings.LLM_PROVIDER).lower()

    # 测试模式：用传入的 config 覆盖一切
    if force_db_config:
        test_api_key = force_db_config.get("api_key", "")
        test_base_url = force_db_config.get("base_url", "")
        test_model = model or force_db_config.get("model", "")
        if not test_model:
            test_model = settings.ARK_CHAT_MODEL
        return ChatOpenAI(model=test_model, api_key=test_api_key,
                          base_url=test_base_url or settings.ARK_BASE_URL,
                          temperature=temperature, request_timeout=60.0, max_retries=2)

    # 从 DB 或 .env 获取 api_key / base_url
    db_api_key = _get_db_cfg("ai_api_key", "")
    db_base_url = _get_db_cfg("ai_base_url", "")

    if p == "giteeai":
        api_key = db_api_key or settings.GITEEAI_API_KEY
        base_url = db_base_url or settings.GITEEAI_BASE_URL
        if not api_key:
            raise ValueError("GITEEAI_API_KEY 未配置（DB 和 .env 均无）")
        return ChatOpenAI(model=model or _get_db_cfg("ai_model") or settings.GITEEAI_CHAT_MODEL,
                          api_key=api_key, base_url=base_url,
                          temperature=temperature, request_timeout=60.0, max_retries=2)
    if p == "ark":
        api_key = db_api_key or settings.ARK_API_KEY
        base_url = db_base_url or settings.ARK_BASE_URL
        if not api_key:
            raise ValueError("ARK_API_KEY 未配置（DB 和 .env 均无）")
        return ChatOpenAI(model=model or _get_db_cfg("ai_model") or settings.ARK_CHAT_MODEL,
                          api_key=api_key, base_url=base_url,
                          temperature=temperature, request_timeout=60.0, max_retries=2)
    if p == "deepseek":
        api_key = db_api_key or settings.DEEPSEEK_API_KEY
        base_url = db_base_url or "https://api.deepseek.com/v1"
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置（DB 和 .env 均无）")
        return ChatOpenAI(model=model or _get_db_cfg("ai_model") or settings.DEEPSEEK_MODEL,
                          api_key=api_key, base_url=base_url,
                          temperature=temperature, request_timeout=60.0, max_retries=2)
    raise ValueError(f"未知 LLM_PROVIDER: {p}")


def clear_llm_cache():
    """配置更新后清除 OpenAI 客户端缓存，使新配置生效"""
    _client_for.cache_clear()
    _async_client_for.cache_clear()
