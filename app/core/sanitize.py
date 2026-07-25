"""审计日志/日志输出脱敏工具

- SecretStr 自动脱敏
- 正则替换常见敏感模式（JWT、API key、手机号、身份证、银行卡、邮箱等）
- 环境变量中配置的密钥值也替换
"""
from __future__ import annotations
import os
import re
from typing import Any


# JWT (三段 base64url): eyJ... 三段用点连，长度 >50
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
# OpenAI/Ark/DeepSeek sk- 开头的 key
_SK_RE = re.compile(r"(sk|pk|rk)-[A-Za-z0-9]{20,}")
# 手机号（中国大陆 11 位）
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# 身份证号（18 位，末位 X/x）
_IDCARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
# 银行卡号（13-19 位连续数字）
_BANKCARD_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
# 邮箱（简单模式）
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Bearer token in headers
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._-]{20,}", re.IGNORECASE)
# 通用 key=secret 模式（api_key=xxx, password=xxx, secret=xxx, token=xxx）
_KV_SECRET_RE = re.compile(
    r'(?i)(api[_-]?key|password|secret|token|access[_-]?key|refresh[_-]?token|authorization)'
    r'\s*[:=]\s*["\']?([^\s"\'<>]{6,})'
)

# 通用密钥模式（高熵 base64/hex 长度 >32）
_HEX_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/=_-]{40,}(?![A-Za-z0-9])")


def mask_value(value: str, replacement: str = "***") -> str:
    """脱敏字符串中的敏感模式"""
    if not isinstance(value, str) or not value:
        return value

    s = value
    # 按"更具体到更通用"的顺序
    s = _BEARER_RE.sub(rf"\1{replacement}", s)
    s = _JWT_RE.sub(replacement, s)
    s = _SK_RE.sub(replacement, s)
    # 邮箱保留首字母和域名
    def _mask_email(m):
        e = m.group(0)
        local, _, domain = e.partition("@")
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "***" + local[-1]
        return f"{masked_local}@{domain}"
    s = _EMAIL_RE.sub(_mask_email, s)
    # 身份证/银行卡/手机号
    s = _IDCARD_RE.sub(lambda m: m.group(0)[:6] + "********" + m.group(0)[-4:], s)
    s = _BANKCARD_RE.sub(lambda m: m.group(0)[:4] + "********" + m.group(0)[-4:] if len(m.group(0)) >= 13 else m.group(0), s)
    s = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], s)
    # key=value 模式
    def _mask_kv(m):
        key = m.group(1)
        return f"{key}={replacement}"
    s = _KV_SECRET_RE.sub(_mask_kv, s)

    return s


def mask_dict(data: Any, replacement: str = "***") -> Any:
    """递归脱敏 dict/list 中的字符串值"""
    if isinstance(data, dict):
        out = {}
        secret_keys = {"password", "secret", "token", "access_token", "refresh_token",
                       "api_key", "authorization", "jwt", "secret_key"}
        for k, v in data.items():
            if isinstance(k, str) and k.lower() in secret_keys and isinstance(v, str) and len(v) > 4:
                out[k] = replacement
            else:
                out[k] = mask_dict(v, replacement)
        return out
    if isinstance(data, list):
        return [mask_dict(item, replacement) for item in data]
    if isinstance(data, str):
        return mask_value(data, replacement)
    return data


def mask_env_values(value: str) -> str:
    """替换环境变量中实际的密钥值（防止密钥值直接出现在日志中）"""
    s = value
    # 遍历可能的密钥环境变量
    for key in ("JWT_SECRET", "FERNET_KEY", "DATABASE_URL", "ARK_API_KEY",
                "DEEPSEEK_API_KEY", "GITEEAI_API_KEY"):
        v = os.environ.get(key, "")
        if v and len(v) >= 8 and v in s:
            s = s.replace(v, "***")
    return s


def sanitize(value: Any) -> Any:
    """统一入口：dict/list/str 都脱敏"""
    if isinstance(value, str):
        return mask_value(mask_env_values(value))
    return mask_dict(value)


def sanitize_log(message: str) -> str:
    """日志字符串脱敏"""
    return mask_value(mask_env_values(str(message)))
