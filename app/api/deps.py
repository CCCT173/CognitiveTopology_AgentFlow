"""公共依赖注入"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db  # noqa: F401
from app.core.security import get_current_user, get_current_user_required_enabled  # noqa: F401
from app.core.exceptions import forbidden, not_found
from app.models.user import User


def get_current_admin(current_user: User = Depends(get_current_user_required_enabled)) -> User:
    """要求当前用户是管理员(super_admin 或 admin)且账号启用"""
    if current_user.role not in ("super_admin", "admin"):
        raise forbidden("需要管理员权限")
    return current_user


def get_current_superadmin(current_user: User = Depends(get_current_user_required_enabled)) -> User:
    """要求当前用户是超级管理员"""
    if current_user.role != "super_admin":
        raise forbidden("需要超级管理员权限")
    return current_user


def is_admin(user: User) -> bool:
    return user.role in ("super_admin", "admin")


def can_access_resource(user: User, owner_id: int | None) -> bool:
    """判断 user 是否能访问某个资源:
    - super_admin / admin 可访问所有资源
    - 普通 user 只能访问自己创建的资源
    """
    if is_admin(user):
        return True
    return owner_id is not None and owner_id == user.user_id


def can_modify_resource(user: User, owner_id: int | None) -> bool:
    """判断 user 是否能修改/删除某个资源"""
    return can_access_resource(user, owner_id)


def ensure_owner_or_admin(user: User, owner_id: int | None, resource_name: str = "资源"):
    """校验所有权, 失败则 403 / 404"""
    if not can_modify_resource(user, owner_id):
        raise forbidden(f"无权访问该{resource_name}")
