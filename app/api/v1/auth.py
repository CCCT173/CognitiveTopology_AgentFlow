"""
认证接口 (改进版)
  POST /api/v1/auth/register      注册(邮箱格式校验 + 可选 bind_admin_id)
  POST /api/v1/auth/login         登录(限流) → 返回 access + refresh token
  POST /api/v1/auth/refresh       用 refresh token 换新 access token
  POST /api/v1/auth/logout        撤销当前 refresh token
  GET  /api/v1/auth/me            当前用户
  POST /api/v1/auth/ping          心跳(仅 enabled 用户)
  PATCH /api/v1/auth/me           修改自己的资料
  POST /api/v1/auth/me/avatar     上传头像(写盘，DB 存 /files/avatars/xxx)
"""
import os
import re
import uuid
import shutil
from fastapi import APIRouter, Depends, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import ok
from app.schemas.user import RegisterIn, LoginIn, LoginOut, UserOut, UserUpdateMe
from app.services import user_service
from app.services import auth_service
from app.core.security import create_token, get_current_user_required_enabled, get_current_user
from app.core.security_utils import login_limiter
from app.core.exceptions import ErrBadRequest, ErrUnauth
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["认证"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ALLOWED_AVATAR_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/register", summary="注册")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    # 邮箱格式基本校验
    if body.email and not EMAIL_RE.match(body.email):
        raise ErrBadRequest("邮箱格式不正确")
    if len(body.password) < 6:
        raise ErrBadRequest("密码至少 6 位")
    if len(body.account) < 3:
        raise ErrBadRequest("账号至少 3 个字符")
    user = user_service.register(db, body)
    token = create_token(user.user_id)
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")[:500]
    refresh = auth_service.issue_refresh_token(db, user.user_id, ip=ip, user_agent=ua)
    return ok(LoginOut(
        token=token, refresh_token=refresh,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    ).model_dump())


@router.post("/login", summary="登录(账号或邮箱 + 密码)")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{body.account}:{ip}"
    login_limiter.check(rate_key)
    try:
        user = user_service.authenticate(db, body.account, body.password)
    except Exception:
        login_limiter.hit(rate_key)
        raise
    login_limiter.reset(rate_key)
    token = create_token(user.user_id)
    ua = request.headers.get("user-agent", "")[:500]
    refresh = auth_service.issue_refresh_token(db, user.user_id, ip=ip, user_agent=ua)
    return ok(LoginOut(
        token=token, refresh_token=refresh,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    ).model_dump())


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh", summary="用 refresh token 换新 access token")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    if not body.refresh_token:
        raise ErrUnauth("缺少 refresh_token")
    try:
        access, new_refresh, user_id = auth_service.refresh_to_new_tokens(db, body.refresh_token)
    except ValueError as e:
        raise ErrUnauth(str(e))
    return ok({
        "token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
    })


class LogoutIn(BaseModel):
    refresh_token: str | None = None
    all_devices: bool = False


@router.post("/logout", summary="登出（撤销 refresh token）")
def logout(body: LogoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.all_devices:
        count = auth_service.revoke_all_for_user(db, user.user_id)
        return ok(msg=f"已撤销全部 {count} 个会话")
    if body.refresh_token:
        auth_service.revoke_refresh_token(db, body.refresh_token)
    return ok(msg="已登出")


@router.get("/me", summary="获取当前登录用户")
def me(user: User = Depends(get_current_user_required_enabled)):
    return ok(UserOut.model_validate(user).model_dump())


@router.post("/ping", summary="心跳(更新在线状态)")
def ping(user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    user_service.touch_last_active(db, user.user_id)
    return ok(msg="pong")


@router.patch("/me", summary="修改自己的资料(昵称/邮箱/头像/密码)")
def update_me(body: UserUpdateMe, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    if body.email and not EMAIL_RE.match(body.email):
        raise ErrBadRequest("邮箱格式不正确")
    updated = user_service.update_me(db, user, body)
    return ok(UserOut.model_validate(updated).model_dump())


@router.post("/me/avatar", summary="上传头像(图片文件,≤2MB)")
async def upload_avatar(file: UploadFile = File(...),
                        user: User = Depends(get_current_user_required_enabled),
                        db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise ErrBadRequest(f"仅支持图片格式: {sorted(ALLOWED_AVATAR_EXT)}")
    # 校验大小 (读一次最多 MAX+1 字节)
    data = await file.read(MAX_AVATAR_SIZE + 1)
    if len(data) > MAX_AVATAR_SIZE:
        raise ErrBadRequest("头像大小不能超过 2MB")
    avatar_dir = str(settings.upload_dir_abs / "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    # 删除旧头像（如果是 /files/avatars/xxx 形式）
    if user.avatar_url and user.avatar_url.startswith("/files/avatars/"):
        old_path = os.path.join(str(settings.upload_dir_abs), user.avatar_url.replace("/files/", "", 1))
        try:
            if os.path.isfile(old_path): os.remove(old_path)
        except OSError:
            pass
    fname = f"u{user.user_id}_{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(avatar_dir, fname)
    with open(fpath, "wb") as f:
        f.write(data)
    avatar_url = f"/files/avatars/{fname}"
    user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)
    return ok(UserOut.model_validate(user).model_dump())
