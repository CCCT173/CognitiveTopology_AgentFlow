"""工作流 API Key 管理 + 外部执行端点

- GET/POST/DELETE /workflows/{id}/api-keys         Key 管理（需 owner 权限）
- POST /execute/{api_key}                           外部调用（无 JWT，用 key 认证）

外部调用示例：
```python
import requests
r = requests.post(
    "http://localhost:8001/api/v1/execute/wf_xxxxxxxxxxxxxxxx",
    json={"inputs": {"query": "hello"}}
)
print(r.json())
```
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, is_admin
from app.core.security import get_current_user_required_enabled
from app.models.user import User
from app.models.workflow_api_key import WorkflowApiKey, generate_wf_key, hash_wf_key
from app.schemas.common import ok
from app.services import workflow_service
from app.schemas.workflow import WorkflowRunIn

router = APIRouter(prefix="/workflows", tags=["工作流 API Key"])
exec_router = APIRouter(prefix="/execute", tags=["工作流外部执行"])


# ============ Key 管理 ============

class ApiKeyCreate(BaseModel):
    name: str = "default"


class ApiKeyOut(BaseModel):
    id: int
    name: str
    api_key: str
    is_active: bool
    expires_at: Optional[str] = None
    calls_count: int
    last_used_at: Optional[str] = None
    created_at: str


def _require_wf_owner(db: Session, wf_id: int, user: User):
    """要求工作流 owner 或 admin"""
    wf = workflow_service.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    if is_admin(user):
        return wf
    from app.services import workflow_permission_service as perm_svc
    role = perm_svc.get_user_role(db, wf_id, user.user_id)
    if role != "owner":
        raise HTTPException(status_code=403, detail="只有 owner 可以管理 API Key")
    return wf


@router.get("/{wf_id}/api-keys", summary="列出工作流 API Key")
def list_keys(wf_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user_required_enabled)):
    _require_wf_owner(db, wf_id, user)
    rows = db.scalars(
        select(WorkflowApiKey).where(WorkflowApiKey.workflow_id == wf_id)
        .order_by(WorkflowApiKey.created_at.desc())
    ).all()
    return ok([{
        "id": r.id, "name": r.name,
        # 只显示 key 前 8 + 后 4 位（无法从哈希反推，用 name 标识）
        "api_key_masked": f"{r.name} (id={r.id})",
        "is_active": r.is_active,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "calls_count": r.calls_count,
        "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        "created_at": r.created_at.isoformat(),
    } for r in rows])


@router.post("/{wf_id}/api-keys", summary="创建 API Key")
def create_key(wf_id: int, body: ApiKeyCreate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user_required_enabled)):
    _require_wf_owner(db, wf_id, user)
    existing = db.scalar(
        select(WorkflowApiKey).where(
            WorkflowApiKey.workflow_id == wf_id,
            WorkflowApiKey.name == body.name,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"同名 key '{body.name}' 已存在")
    plain_key = generate_wf_key()
    key = WorkflowApiKey(
        workflow_id=wf_id, name=body.name,
        api_key_hash=hash_wf_key(plain_key),
        api_key="",  # 不持久化明文
        created_by=user.user_id,
    )
    db.add(key); db.commit(); db.refresh(key)
    return ok({
        "id": key.id, "name": key.name,
        "api_key": plain_key,
        "is_active": key.is_active,
        "warning": "请立即保存此 key，后续不再返回完整值",
        "execute_url": f"/api/v1/execute/{plain_key}",
    })


@router.delete("/{wf_id}/api-keys/{key_id}", summary="删除 API Key")
def delete_key(wf_id: int, key_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user_required_enabled)):
    _require_wf_owner(db, wf_id, user)
    key = db.get(WorkflowApiKey, key_id)
    if not key or key.workflow_id != wf_id:
        raise HTTPException(status_code=404, detail="key 不存在")
    db.delete(key); db.commit()
    return ok(msg="已删除")


class ToggleKeyIn(BaseModel):
    is_active: bool


@router.post("/{wf_id}/api-keys/{key_id}/toggle", summary="启用/禁用 Key")
def toggle_key(wf_id: int, key_id: int, body: ToggleKeyIn,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user_required_enabled)):
    _require_wf_owner(db, wf_id, user)
    key = db.get(WorkflowApiKey, key_id)
    if not key or key.workflow_id != wf_id:
        raise HTTPException(status_code=404, detail="key 不存在")
    key.is_active = body.is_active
    db.commit()
    return ok({"is_active": key.is_active})


# ============ 外部执行端点（无 JWT） ============

class ExecuteIn(BaseModel):
    inputs: dict = {}         # Dify 风格别名
    input: dict | None = None # 原生字段
    variables: dict = {}
    user: Optional[str] = None


@exec_router.post("/{api_key}", summary="通过 API Key 执行工作流（外部调用）")
async def execute_by_key(
    api_key: str,
    body: ExecuteIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """外部脚本调用入口。
    - 不需要 JWT，用 URL 里的 api_key 认证
    - 支持 Dify 风格的 inputs 参数
    """
    # 查 key（按哈希）
    key = db.scalar(select(WorkflowApiKey).where(WorkflowApiKey.api_key_hash == hash_wf_key(api_key)))
    if not key:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    if not key.is_active:
        raise HTTPException(status_code=403, detail="API Key 已禁用")
    if key.expires_at and key.expires_at < utc_now():
        raise HTTPException(status_code=403, detail="API Key 已过期")
    # 查工作流
    wf = workflow_service.get_workflow(db, key.workflow_id)
    if not wf or not wf.enabled:
        raise HTTPException(status_code=404, detail="工作流不存在或已禁用")
    # 更新统计
    from app.core.time import utc_now_naive
    ip = request.client.host if request.client else ""
    key.calls_count += 1
    key.last_used_at = utc_now_naive()
    key.last_used_ip = ip[:64]
    # 构造 WorkflowRunIn
    run_input = body.input if body.input is not None else body.inputs
    run_in = WorkflowRunIn(
        input=run_input,
        variables=body.variables,
        sync=True,
    )
    try:
        result = workflow_service.run_workflow(db, key.workflow_id, run_in, user_id=key.created_by or 0)
    except Exception as e:
        db.commit()
        msg = str(e)
        status = 400 if any(k in msg for k in ("工作流", "为空", "不存在", "未启用", "invalid", "空")) else 500
        code = "WORKFLOW_INVALID" if status == 400 else "INTERNAL_ERROR"
        raise HTTPException(status_code=status, detail={"code": code, "message": msg})
    db.commit()
    return {
        "workflow_id": key.workflow_id,
        "workflow_name": wf.name,
        "task_id": result.get("run_id", ""),
        "status": result.get("status", "success"),
        "outputs": result.get("output", {}),
        "elapsed_ms": result.get("elapsed_ms", 0),
    }


def utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
