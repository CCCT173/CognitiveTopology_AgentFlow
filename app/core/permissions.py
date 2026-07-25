"""
基于角色的权限矩阵 (RBAC)
- super_admin: 唯一超级管理员, 拥有全部权限
- admin:       次级管理员, 除 admin.manage(管理次级管理员) / user.delete(删除普通用户) 外全部
- user:        普通用户, 只能管理自己的资源 + 修改自己资料

权限点命名: <domain>.<action>
  - admin.manage  管理次级管理员
  - user.delete   删除普通用户
  - agent.all / agent.own.all / agent.own.read
  - kb.all / kb.own.all
  - group.all / group.own
通配符 "*" 表示全部
"""
from fastapi import Depends

from app.core.exceptions import ErrForbidden
from app.core.security import get_current_user
from app.models.user import User


# 角色 -> 权限集合
ROLE_PERMS: dict[str, set[str]] = {
    "super_admin": {"*"},
    "admin": {
        "agent.all", "kb.all", "user.update_own", "user.list",
        "group.all", "chat.all",
    },
    "user": {
        "agent.own.all", "kb.own.all", "user.update_own", "user.list",
        "group.all", "chat.own",
    },
}


def _has_perm(role: str, perm: str) -> bool:
    perms = ROLE_PERMS.get(role, set())
    return "*" in perms or perm in perms


def require_perm(perm: str):
    """FastAPI 依赖工厂: 要求当前用户拥有指定权限"""
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if not _has_perm(user.role, perm):
            raise ErrForbidden(f"需要权限: {perm}")
        return user
    return _dep


def can_admin_manage_admins(user: User) -> bool:
    """是否可以管理次级管理员(仅 super_admin)"""
    return _has_perm(user.role, "admin.manage")


def can_delete_user(user: User, target: User) -> bool:
    """
    是否可以删除目标用户:
      - super_admin: 可删任何人
      - admin: 不可删任何人(按需求排除删除普通用户)
      - user: 不可删
    """
    if _has_perm(user.role, "*"):
        return True
    return False


def can_manage_agent(user: User, owner_id: int) -> bool:
    """是否可以管理(改/删)该 agent"""
    if _has_perm(user.role, "agent.all"):
        return True
    return _has_perm(user.role, "agent.own.all") and user.user_id == owner_id


def can_manage_kb(user: User, owner_id: int) -> bool:
    if _has_perm(user.role, "kb.all"):
        return True
    return _has_perm(user.role, "kb.own.all") and user.user_id == owner_id
