"""Refresh token 服务

- 签发 refresh token（明文返回，存 SHA256 哈希到 DB）
- 校验：已用/已撤/过期均拒绝
- rotate：校验通过后作废旧 token，签发新 access + refresh 对
- revoke_all：登出设备/全部
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.core.config import settings
from app.core.time import utc_now_naive
from app.core.security import create_token
from app.models.refresh_token import RefreshToken


def _hash(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user_id: int, *, device: str = "",
                        ip: str = "", user_agent: str = "") -> str:
    """签发新的 refresh token，返回明文 token（不存明文）"""
    plain = secrets.token_urlsafe(48)
    token = f"rt_{plain}"
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_hash(token),
        device=device[:200], ip=ip[:64], user_agent=user_agent[:500],
        expires_at=utc_now_naive() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    db.add(rt)
    db.commit()
    return token


def refresh_to_new_tokens(db: Session, refresh_token: str) -> tuple[str, str, int]:
    """用 refresh token 换新的 access + refresh token 对（rotation）。
    返回 (access_token, new_refresh_token, user_id)。失败抛 ValueError。
    """
    h = _hash(refresh_token)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == h))
    if rt is None:
        raise ValueError("refresh token 不存在")
    if rt.revoked:
        raise ValueError("refresh token 已撤销")
    if rt.used:
        # token 重用检测：该 token 已被用（可能被盗），撤销该用户所有 token
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == rt.user_id, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        db.commit()
        raise ValueError("refresh token 重用检测，已撤销所有会话，请重新登录")
    if rt.expires_at < utc_now_naive():
        raise ValueError("refresh token 已过期")

    # 标记旧 token 已用
    new_rt = issue_refresh_token(db, rt.user_id, device=rt.device, ip=rt.ip, user_agent=rt.user_agent)
    rt.used = True
    rt.replaced_by = _hash(new_rt)
    # 新 access token
    access = create_token(rt.user_id)
    db.commit()
    return access, new_rt, rt.user_id


def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
    """撤销单个 refresh token（登出）"""
    h = _hash(refresh_token)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == h))
    if rt is None:
        return False
    rt.revoked = True
    db.commit()
    return True


def revoke_all_for_user(db: Session, user_id: int) -> int:
    """撤销某用户所有 refresh token（登出所有设备）"""
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
            RefreshToken.used == False,
        )
    ).all()
    for r in rows:
        r.revoked = True
    db.commit()
    return len(rows)


def cleanup_expired(db: Session) -> int:
    """清理过期/已用/已撤销的 refresh token（定时任务调用）"""
    from sqlalchemy import delete
    now = utc_now_naive()
    result = db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked == True)
        )
    )
    db.commit()
    return result.rowcount
