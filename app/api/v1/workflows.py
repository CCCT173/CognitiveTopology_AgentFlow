"""
工作流接口 (带所有权校验)
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, ensure_owner_or_admin, is_admin
from app.schemas.common import ok
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowOut, WorkflowRunIn, WorkflowRunOut
from app.schemas.agent import ToggleEnable
from app.services import workflow_service
from app.core.security import get_current_user_required_enabled
from app.models.user import User

router = APIRouter(prefix="/workflows", tags=["工作流"])


@router.get("", summary="工作流列表")
def list_workflows(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    category: Optional[str] = Query(None, description="按分类过滤"),
    enabled_only: bool = Query(False, description="只看已启用"),
    mine: bool = Query(False, description="只看我创建的"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    if is_admin(user):
        owner_id = user.user_id if mine else None
    else:
        owner_id = user.user_id  # 普通用户强制只看自己的
    data = [
        WorkflowOut.model_validate(w).model_dump()
        for w in workflow_service.list_workflows(db, keyword, category, owner_id, enabled_only)
    ]
    return ok(data)


@router.post("", summary="创建工作流")
def create_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    obj = workflow_service.create_workflow(db, user, body)
    # 自动给创建者 owner 权限
    from app.services import workflow_permission_service as perm_svc
    perm_svc.ensure_creator_owner(db, obj.id, user.user_id)
    return ok(WorkflowOut.model_validate(obj).model_dump())


def _get_checked(db: Session, wf_id: int, user: User, required_role: str = "owner"):
    """获取工作流并校验权限（viewer/editor/owner）。owner/admin 满足一切。"""
    wf = workflow_service.get_workflow(db, wf_id)
    if not wf:
        from app.core.exceptions import ErrNotFound
        raise ErrNotFound("工作流")
    from app.services import workflow_permission_service as perm_svc
    from app.api.deps import is_admin
    if perm_svc.check_permission(db, wf_id, user.user_id, required_role, is_admin=is_admin(user)):
        return wf
    from app.core.exceptions import ErrForbidden
    raise ErrForbidden(f"需要 {required_role} 权限")


def _get_checked_owner(db: Session, wf_id: int, user: User):
    return _get_checked(db, wf_id, user, "owner")


def _get_checked_editor(db: Session, wf_id: int, user: User):
    return _get_checked(db, wf_id, user, "editor")


def _get_checked_viewer(db: Session, wf_id: int, user: User):
    return _get_checked(db, wf_id, user, "viewer")


@router.get("/{wf_id}", summary="工作流详情")
def get_workflow(wf_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _get_checked_viewer(db, wf_id, user)
    return ok(WorkflowOut.model_validate(workflow_service.get_workflow(db, wf_id)).model_dump())


@router.patch("/{wf_id}", summary="更新工作流")
def update_workflow(wf_id: int, body: WorkflowUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user_required_enabled)):
    _get_checked_editor(db, wf_id, user)
    # 乐观锁：body.expected_version 与 wf.version 必须匹配
    expected = getattr(body, "expected_version", None)
    wf = workflow_service.get_workflow(db, wf_id)
    if expected is not None and getattr(wf, "version", 1) != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"版本冲突: 期望 v{expected}, 实际 v{wf.version}")
    obj = workflow_service.update_workflow(db, wf_id, body)
    # 版本自增
    obj.version = getattr(obj, "version", 1) + 1
    db.commit()
    return ok(WorkflowOut.model_validate(obj).model_dump())


@router.delete("/{wf_id}", summary="删除工作流")
def delete_workflow(wf_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _get_checked_owner(db, wf_id, user)
    workflow_service.delete_workflow(db, wf_id)
    return ok(msg="已删除")


@router.post("/{wf_id}/toggle", summary="启用/禁用工作流")
def toggle(wf_id: int, body: ToggleEnable, db: Session = Depends(get_db),
           user: User = Depends(get_current_user_required_enabled)):
    _get_checked_owner(db, wf_id, user)
    obj = workflow_service.toggle_workflow(db, wf_id, body.enabled)
    return ok(WorkflowOut.model_validate(obj).model_dump())


@router.post("/{wf_id}/run", summary="执行工作流")
def run(wf_id: int, body: WorkflowRunIn, 
        async_mode: bool = Query(False, description="是否异步执行"),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user_required_enabled)):
    _get_checked_viewer(db, wf_id, user)
    if async_mode:
        # 异步执行：立即返回 run_id，后台执行
        result = workflow_service.run_workflow_async(wf_id, body, user_id=user.user_id)
        return ok(result)
    else:
        # 同步执行：等待工作流完成
        result = workflow_service.run_workflow(db, wf_id, body, user_id=user.user_id)
        return ok(WorkflowRunOut(**result).model_dump())


@router.get("/{wf_id}/runs", summary="工作流运行历史")
def list_runs(wf_id: int, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
              user: User = Depends(get_current_user_required_enabled)):
    _get_checked_viewer(db, wf_id, user)
    runs = workflow_service.list_runs(db, wf_id=wf_id, limit=limit)
    return ok([{
        "id": r.id, "run_id": r.run_id, "workflow_id": r.workflow_id,
        "workflow_name": r.workflow_name, "status": r.status,
        "elapsed_ms": r.elapsed_ms, "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in runs])


@router.get("/runs/{run_id}", summary="运行详情")
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    r = workflow_service.get_run(db, run_id)
    _get_checked_viewer(db, r.workflow_id, user)
    return ok({
        "id": r.id, "run_id": r.run_id, "workflow_id": r.workflow_id,
        "workflow_name": r.workflow_name, "status": r.status,
        "input_data": r.input_data, "output_data": r.output_data,
        "logs": r.logs, "node_outputs": r.node_outputs, "error": r.error,
        "elapsed_ms": r.elapsed_ms,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    })


# ============ 版本管理 ============

@router.get("/{wf_id}/versions", summary="版本历史")
def list_versions(wf_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _get_checked_viewer(db, wf_id, user)
    from app.models.versioning import WorkflowVersion
    from sqlalchemy import select
    rows = db.scalars(
        select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf_id)
        .order_by(WorkflowVersion.version.desc()).limit(100)
    ).all()
    return ok([{
        "id": v.id, "version": v.version, "name": v.name,
        "description": v.description, "changelog": v.changelog,
        "published_by": v.published_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in rows])


class PublishIn(BaseModel):
    name: str = ""
    description: str = ""
    changelog: str = ""


@router.post("/{wf_id}/versions", summary="发布版本快照")
def publish_version(wf_id: int, body: PublishIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user_required_enabled)):
    _get_checked_editor(db, wf_id, user)
    wf = workflow_service.get_workflow(db, wf_id)
    from app.models.versioning import WorkflowVersion
    from sqlalchemy import select, func
    import json
    next_v = db.scalar(select(func.coalesce(func.max(WorkflowVersion.version), 0)).where(
        WorkflowVersion.workflow_id == wf_id)) + 1
    snap = WorkflowVersion(
        workflow_id=wf_id, version=next_v,
        name=body.name or f"v{next_v}",
        description=body.description or wf.description or "",
        definition_json=json.dumps(wf.definition or {}, ensure_ascii=False),
        changelog=body.changelog,
        published_by=user.user_id,
    )
    db.add(snap); db.commit(); db.refresh(snap)
    return ok({"version": next_v, "id": snap.id})


class RollbackIn(BaseModel):
    version: int


@router.post("/{wf_id}/rollback", summary="回滚到指定版本")
def rollback_version(wf_id: int, body: RollbackIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user_required_enabled)):
    _get_checked_editor(db, wf_id, user)
    from app.models.versioning import WorkflowVersion
    import json
    snap = db.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == wf_id, WorkflowVersion.version == body.version
        )
    )
    if not snap:
        from app.core.exceptions import ErrNotFound
        raise ErrNotFound("版本")
    wf = workflow_service.get_workflow(db, wf_id)
    try:
        wf.definition = json.loads(snap.definition_json)
    except (json.JSONDecodeError, TypeError):
        wf.definition = {}
    wf.version = (getattr(wf, "version", 1) or 1) + 1
    db.commit()
    return ok({"current_version": wf.version, "rolled_back_to": body.version})
