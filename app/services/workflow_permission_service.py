"""工作流共享权限服务

- grant_permission：给用户授角色
- revoke_permission：撤销
- list_permissions：列出某工作流的共享列表
- check_permission：检查用户对某工作流的角色
- get_accessible_workflow_ids：用户能访问的工作流 id 集合
"""
from __future__ import annotations
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from app.models.workflow_permission import (
    WorkflowPermission, ROLE_VIEWER, ROLE_EDITOR, ROLE_OWNER, role_at_least,
)


def grant_permission(db: Session, workflow_id: int, user_id: int, role: str,
                     granted_by: int = 0) -> WorkflowPermission:
    """授予或更新权限"""
    if role not in (ROLE_VIEWER, ROLE_EDITOR, ROLE_OWNER):
        raise ValueError(f"invalid role: {role}")
    existing = db.scalar(
        select(WorkflowPermission).where(
            WorkflowPermission.workflow_id == workflow_id,
            WorkflowPermission.user_id == user_id,
        )
    )
    if existing:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing
    perm = WorkflowPermission(
        workflow_id=workflow_id, user_id=user_id, role=role, granted_by=granted_by,
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def revoke_permission(db: Session, workflow_id: int, user_id: int) -> bool:
    """撤销权限（不能撤销 owner，owner 至少保留一个，owner 转移用 grant 传新 owner）"""
    perm = db.scalar(
        select(WorkflowPermission).where(
            WorkflowPermission.workflow_id == workflow_id,
            WorkflowPermission.user_id == user_id,
        )
    )
    if not perm:
        return False
    if perm.role == ROLE_OWNER:
        # 检查是否最后一个 owner
        owners = db.scalar(
            select(func.count(WorkflowPermission.id)).where(
                WorkflowPermission.workflow_id == workflow_id,
                WorkflowPermission.role == ROLE_OWNER,
            )
        )
        if owners <= 1:
            raise ValueError("不能撤销最后一个 owner 的权限，请先转移所有权")
    db.delete(perm)
    db.commit()
    return True


def list_permissions(db: Session, workflow_id: int) -> list[dict]:
    """列出工作流的所有共享用户"""
    rows = db.scalars(
        select(WorkflowPermission).where(WorkflowPermission.workflow_id == workflow_id)
    ).all()
    # join users 表拿 username/account
    from app.models.user import User
    result = []
    for p in rows:
        u = db.get(User, p.user_id)
        result.append({
            "user_id": p.user_id,
            "username": u.username if u else f"user#{p.user_id}",
            "account": u.account if u else "",
            "role": p.role,
        })
    return result


def get_user_role(db: Session, workflow_id: int, user_id: int, is_admin: bool = False) -> str | None:
    """获取用户对某工作流的最高角色，admin 直接返回 owner"""
    if is_admin:
        return ROLE_OWNER
    perm = db.scalar(
        select(WorkflowPermission).where(
            WorkflowPermission.workflow_id == workflow_id,
            WorkflowPermission.user_id == user_id,
        )
    )
    return perm.role if perm else None


def check_permission(db: Session, workflow_id: int, user_id: int, required_role: str,
                     is_admin: bool = False) -> bool:
    """检查用户是否有至少 required_role"""
    role = get_user_role(db, workflow_id, user_id, is_admin=is_admin)
    if not role:
        return False
    return role_at_least(role, required_role)


def ensure_creator_owner(db: Session, workflow_id: int, user_id: int):
    """工作流创建后调用：确保创建者有 owner 权限（幂等）"""
    existing = db.scalar(
        select(WorkflowPermission).where(
            WorkflowPermission.workflow_id == workflow_id,
            WorkflowPermission.user_id == user_id,
        )
    )
    if existing:
        if existing.role != ROLE_OWNER:
            existing.role = ROLE_OWNER
            db.commit()
        return
    db.add(WorkflowPermission(
        workflow_id=workflow_id, user_id=user_id, role=ROLE_OWNER,
    ))
    db.commit()


def list_accessible_workflow_ids(db: Session, user_id: int, is_admin: bool = False) -> set[int]:
    """用户能访问的工作流 id 集合（用于 list_workflows 过滤）。
    admin 返回 None 表示无限制。
    """
    if is_admin:
        return set()  # 空集合表示不限制（调用方判断）
    rows = db.scalars(
        select(WorkflowPermission.workflow_id).where(WorkflowPermission.user_id == user_id)
    ).all()
    return set(rows)
