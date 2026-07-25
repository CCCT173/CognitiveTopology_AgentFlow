"""
鉴权 & 安全工具
- hash_password / verify_password: bcrypt 密码哈希
- create_token / decode_token:    JWT 签发/校验(payload 内含 user_id)
- get_current_user:               FastAPI 依赖, 从 Authorization 解析出当前用户
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ErrUnauth
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- 密码哈希 (bcrypt) ----------
def hash_password(plain: str) -> str:
    """明文密码 → bcrypt 哈希字符串 (含盐)"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------
def create_token(user_id: int, minutes: int | None = None) -> str:
    """根据 user_id 签发 JWT; payload = {"sub": user_id, "exp": ...}"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes or settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> int:
    """校验 JWT 并返回 user_id; 失败抛 401"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            raise ErrUnauth("无效token")
        # 兼容旧格式 token: sub 可能是 dict/字符串数字/用户名
        if isinstance(uid, dict):
            uid = uid.get("user_id") or uid.get("sub")
        if isinstance(uid, str):
            # 纯数字字符串 → int, 否则可能是旧 token 用 account 作为 sub
            if uid.isdigit():
                uid = int(uid)
            else:
                # 旧 token: sub 是 account 字符串, 无法直接用, 视为过期
                raise ErrUnauth("token已过期，请重新登录")
        if not isinstance(uid, int):
            raise ErrUnauth("无效token")
        return uid
    except jwt.ExpiredSignatureError:
        raise ErrUnauth("token已过期") from None
    except jwt.InvalidTokenError:
        raise ErrUnauth("无效token") from None
    except (ValueError, TypeError):
        raise ErrUnauth("无效token") from None


# ---------- 依赖: 当前用户 ----------
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    从 Authorization: Bearer <token> 解析出当前登录用户。
    注意: 与 verify_token 不同, 此依赖用于需要识别"是谁"的业务接口;
          verify_token 只是简单校验静态 API_TOKEN(管理接口用)。
    """
    if creds is None:
        raise ErrUnauth("缺少登录凭证")
    user_id = decode_token(creds.credentials)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise ErrUnauth("用户不存在或已被禁用")
    return user


async def get_current_user_required_enabled(user: User = Depends(get_current_user)) -> User:
    """需要用户 enabled 才能访问"""
    if not user.enabled:
        raise ErrUnauth("账号未启用")
    return user
