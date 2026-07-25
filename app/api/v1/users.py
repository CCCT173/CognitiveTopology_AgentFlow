"""
用户管理接口(管理员)
  GET    /api/v1/users                 用户列表（组织树结构）
  GET    /api/v1/users/flat            扁平用户列表（用于选择器）
  GET    /api/v1/users/admins          管理员列表(注册时选择绑定管理员用, 登录后可访问)
  POST   /api/v1/users                 管理员创建用户
  PATCH  /api/v1/users/{id}            修改用户(上级/部门/角色/启用等)
  DELETE /api/v1/users/{id}            删除用户
  POST   /api/v1/users/{id}/role       设置角色
  POST   /api/v1/users/{id}/enabled    启用/禁用用户
  POST   /api/v1/users/{id}/bind       重新绑定管理员(兼容旧接口)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin, get_current_superadmin
from app.schemas.common import ok
from app.schemas.user import UserOnlineOut, UserOut, RegisterIn, UserCreate, UserUpdate, UserTreeNode
from app.services import user_service
from app.core.security import get_current_user_required_enabled
from app.models.user import User
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["用户管理"])


class RoleIn(BaseModel):
    role: str


class EnabledIn(BaseModel):
    enabled: bool


class BindIn(BaseModel):
    admin_id: int | None = None


@router.get("/tree", summary="用户组织树")
def list_users_tree(
    keyword: str | None = Query(None, description="按用户名/账号/邮箱/职位/部门模糊搜索"),
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user_required_enabled),
):
    """返回 viewer 可见范围内的组织树。
    - super_admin: 全公司树
    - admin: 以自己为根的子树
    - user: 仅自己
    """
    tree = user_service.list_users_tree(db, viewer, keyword)
    return ok([t.model_dump() for t in tree])


@router.get("/flat", summary="扁平用户列表(用于上级选择器)")
def list_users_flat(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_admin),
):
    """返回 viewer 可见范围内的扁平用户列表（id/label）。"""
    tree = user_service.list_users_tree(db, viewer, keyword)
    flat: list[dict] = []

    def walk(nodes: list[UserTreeNode], depth: int = 0):
        for n in nodes:
            flat.append({
                "user_id": n.user_id,
                "username": n.username,
                "account": n.account,
                "title": n.title,
                "department": n.department,
                "role": n.role,
                "avatar_url": n.avatar_url,
                "email": n.email,
                "manager_id": n.manager_id,
                "depth": depth,
            })
            walk(n.children, depth + 1)
    walk(tree)
    return ok(flat)


@router.get("", summary="用户列表(扁平)")
def list_users(
    keyword: str | None = Query(None, description="按用户名/账号/邮箱模糊搜索"),
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_admin),
):
    users = user_service.list_users(db, viewer, keyword)
    return ok([
        UserOnlineOut(
            **{**UserOnlineOut.model_validate(u).model_dump(exclude={"online", "last_active_at"}),
               "online": user_service.is_online(u),
               "last_active_at": u.last_active_at,
               "bind_admin_id": u.bind_admin_id,
               "manager_id": u.manager_id,
               "department": u.department,
               "title": u.title,
               "enabled": u.enabled,
               "role": u.role}
        ).model_dump() for u in users
    ])


@router.get("/admins", summary="管理员列表(注册时选择绑定管理员用)")
def list_admins_for_register(db: Session = Depends(get_db)):
    from sqlalchemy import select
    admins = db.scalars(select(User).where(User.role.in_(("admin", "super_admin")), User.enabled.is_(True))).all()
    return ok([{"user_id": a.user_id, "username": a.username, "account": a.account, "role": a.role} for a in admins])


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_admin),
):
    user_service.admin_delete_user(db, operator, user_id)
    return ok(msg="已删除")


@router.post("/{user_id}/role", summary="设置用户角色(仅超级管理员)")
def set_role(
    user_id: int,
    body: RoleIn,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_superadmin),
):
    u = user_service.admin_set_role(db, operator, user_id, body.role)
    return ok({"user_id": u.user_id, "role": u.role, "bind_admin_id": u.bind_admin_id})


@router.post("/{user_id}/enabled", summary="启用/禁用用户")
def set_enabled(
    user_id: int,
    body: EnabledIn,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_admin),
):
    u = user_service.admin_set_enabled(db, operator, user_id, body.enabled)
    return ok({"user_id": u.user_id, "enabled": u.enabled}, msg=f"已{'启用' if u.enabled else '禁用'}")


@router.post("/{user_id}/bind", summary="重新绑定管理员(兼容)")
def bind_user(
    user_id: int,
    body: BindIn,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_admin),
):
    u = user_service.admin_bind_user(db, operator, user_id, body.admin_id)
    return ok({"user_id": u.user_id, "bind_admin_id": u.bind_admin_id})


@router.patch("/{user_id}", summary="修改用户(上级/部门/角色/启用/密码等)")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_admin),
):
    u = user_service.admin_update_user(db, operator, user_id, body)
    return ok(UserOut.model_validate(u).model_dump(), msg="已更新")


@router.post("", summary="管理员创建用户")
def admin_create(
    body: UserCreate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_admin),
):
    u = user_service.admin_create_user_v2(db, operator, body)
    return ok(UserOut.model_validate(u).model_dump(), msg="已创建")
