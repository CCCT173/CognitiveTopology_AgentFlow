"""HITL (Human-In-The-Loop) 待确认任务的 API 端点"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ok
from app.services import hitl as hitl_service


router = APIRouter(prefix="/hitl", tags=["HITL 待确认"])


class ConfirmIn(BaseModel):
    note: str = ""


class DenyIn(BaseModel):
    reason: str = ""


@router.get("/pending", summary="列出当前用户待处理的确认")
def list_pending(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 顺便清理过期的
    hitl_service.expire_old(db)
    return ok(hitl_service.list_pending(db, user.user_id))


@router.post("/{cid}/confirm", summary="确认执行")
def confirm(cid: int, body: ConfirmIn, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    res = hitl_service.confirm(db, cid, user.user_id, note=body.note)
    if not res["ok"]:
        raise HTTPException(status_code=400, detail=res.get("error", "confirm failed"))
    return ok(res)


@router.post("/{cid}/deny", summary="拒绝执行")
def deny(cid: int, body: DenyIn, db: Session = Depends(get_db),
         user: User = Depends(get_current_user)):
    res = hitl_service.deny(db, cid, user.user_id, reason=body.reason)
    if not res["ok"]:
        raise HTTPException(status_code=400, detail=res.get("error", "deny failed"))
    return ok(res)
