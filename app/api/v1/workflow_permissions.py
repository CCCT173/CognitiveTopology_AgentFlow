"""工作流共享权限 API

GET  /api/v1/workflows/{wf_id}/permissions     列出共享
POST /api/v1/workflows/{wf_id}/permissions     授权 {user_id, role}
DELETE /api/v1/workflows/{wf_id}/permissions/{user_id}  撤销
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import workflow_permission_service as perm_svc
from app.services import workflow_service
from app.schemas.common import ok

router = APIRouter(prefix="/workflows", tags=["工作流共享"])


class GrantIn(BaseModel):
    user_id: int
    role: str  # viewer / editor / owner


def _get_wf_or_404(db: Session, wf_id: int):
    wf = workflow_service.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return wf


def _require_owner(db: Session, wf_id: int, user: User):
    """要求是 owner 或 admin"""
    from app.api.deps import is_admin
    if is_admin(user):
        return
    role = perm_svc.get_user_role(db, wf_id, user.user_id)
    if role != "owner":
        raise HTTPException(status_code=403, detail="只有 owner 可以管理共享")


@router.get("/{wf_id}/permissions", summary="列出工作流共享权限")
def list_permissions(wf_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_wf_or_404(db, wf_id)
    _require_owner(db, wf_id, user)
    return ok(perm_svc.list_permissions(db, wf_id))


@router.post("/{wf_id}/permissions", summary="授权用户访问")
def grant(wf_id: int, body: GrantIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wf = _get_wf_or_404(db, wf_id)
    _require_owner(db, wf_id, user)
    # 目标用户必须存在
    from app.models.user import User as UserModel
    target = db.get(UserModel, body.user_id)
    if not target:
        raise HTTPException(status_code=400, detail=f"用户 {body.user_id} 不存在")
    try:
        perm = perm_svc.grant_permission(
            db, wf_id, body.user_id, body.role, granted_by=user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 授权 owner 时更新 created_by
    if body.role == "owner" and wf.created_by != body.user_id:
        # 不自动改 created_by，保留原创建者标记；owner 权限等价
        pass
    return ok({"user_id": perm.user_id, "role": perm.role})


@router.delete("/{wf_id}/permissions/{target_user_id}", summary="撤销授权")
def revoke(wf_id: int, target_user_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    _get_wf_or_404(db, wf_id)
    _require_owner(db, wf_id, user)
    try:
        ok_ = perm_svc.revoke_permission(db, wf_id, target_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok_:
        raise HTTPException(status_code=404, detail="未授权给该用户")
    return ok(msg="已撤销")
