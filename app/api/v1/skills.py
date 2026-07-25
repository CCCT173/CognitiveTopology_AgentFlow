"""技能 (Skill) 管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db, ensure_owner_or_admin, is_admin
from app.core.security import get_current_user_required_enabled
from app.core.exceptions import ErrBadRequest, ErrNotFound, ErrForbidden
from app.models.user import User
from app.models.skill import Skill
from app.schemas.common import ok
from app.schemas.skill import (
    SkillCreate, SkillUpdate, SkillResponse, SkillDetail,
    SkillTestRequest, SkillTestResponse,
)
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skills", tags=["技能管理"])


def _out(s: Skill) -> dict:
    return {
        "id": s.id, "name": s.name, "description": s.description,
        "version": s.version, "author": s.author, "category": s.category or "",
        "tags": s.tags or [], "entry_point": s.entry_point, "code": s.code,
        "config": s.config or {}, "is_builtin": s.is_builtin, "is_active": s.is_active,
        "usage_count": s.usage_count, "last_used_at": s.last_used_at,
        "created_by": s.created_by, "created_at": s.created_at, "updated_at": s.updated_at,
    }


def _detail(s: Skill) -> dict:
    d = _out(s)
    d["content"] = s.content or ""
    return d


def _check_owner(user: User, s: Skill):
    """内置 skill 不允许普通用户改,但 admin/super_admin 可管理; user 只能改自己创建的非内置 skill"""
    if s.is_builtin and not is_admin(user):
        raise ErrForbidden("内置技能不可修改")
    ensure_owner_or_admin(user, s.created_by, "技能")


@router.get("", summary="获取技能列表")
def list_skills(
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    mine: bool = Query(False, description="true=只返回我创建的 (内置技能始终可见)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required_enabled),
):
    skills, _total = SkillService.list_skills(
        db, category=category, tag=tag, keyword=keyword,
        is_active=is_active, is_builtin=None, skip=0, limit=500,
        owner_id=None if is_admin(current_user) and not mine else current_user.user_id,
    )
    return ok([_out(s) for s in skills])


@router.get("/categories", summary="获取技能分类统计")
def get_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    return ok(SkillService.get_skill_categories(db))


@router.get("/{skill_id}", summary="获取技能详情")
def get_skill(skill_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    s = SkillService.get_skill(db, skill_id)
    if not s:
        raise ErrNotFound("技能不存在")
    _check_owner(current_user, s) if not s.is_builtin else None
    return ok(_detail(s))


@router.post("", summary="创建技能")
def create_skill(body: SkillCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    if SkillService.get_skill_by_name(db, body.name):
        raise ErrBadRequest(f"技能 '{body.name}' 已存在")
    s = SkillService.create_skill(db, body)
    s.created_by = current_user.user_id
    db.commit(); db.refresh(s)
    return ok(_detail(s), msg="创建成功")


@router.put("/{skill_id}", summary="更新技能")
def update_skill(skill_id: int, body: SkillUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    s = SkillService.get_skill(db, skill_id)
    if not s:
        raise ErrNotFound("技能不存在")
    _check_owner(current_user, s)
    s = SkillService.update_skill(db, s, body)
    return ok(_detail(s), msg="已更新")


@router.delete("/{skill_id}", summary="删除技能")
def delete_skill(skill_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    s = SkillService.get_skill(db, skill_id)
    if not s:
        raise ErrNotFound("技能不存在")
    if s.is_builtin:
        raise ErrForbidden("内置技能不可删除")
    ensure_owner_or_admin(current_user, s.created_by, "技能")
    SkillService.delete_skill(db, skill_id)
    return ok(msg="已删除")


@router.post("/{skill_id}/test", summary="测试运行技能")
def test_skill(skill_id: int, body: SkillTestRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    s = SkillService.get_skill(db, skill_id)
    if not s:
        raise ErrNotFound("技能不存在")
    if not s.is_builtin:
        _check_owner(current_user, s)
    res = SkillService.test_skill(db, s, body)
    res["elapsed_ms"] = int(res.get("execution_time", 0) * 1000)
    res.setdefault("logs", [])
    res.setdefault("success", False)
    return ok(res)


@router.post("/import", summary="导入技能")
async def import_skill(
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    format: str = Form("markdown"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required_enabled),
):
    if not file and not content:
        raise ErrBadRequest("请提供技能内容或上传文件")
    try:
        if file and file.filename and file.filename.lower().endswith('.zip'):
            raw = await file.read()
            s = SkillService.import_skill_from_zip(db, raw)
        elif file:
            content = (await file.read()).decode("utf-8", errors="replace")
            s = SkillService.import_skill_from_content(db, content, format)
        else:
            s = SkillService.import_skill_from_content(db, content or '', format)
        s.created_by = current_user.user_id
        db.commit(); db.refresh(s)
    except Exception as e:
        raise ErrBadRequest(f"导入失败: {e}")
    return ok(_detail(s), msg="导入成功")


@router.post("/{skill_id}/toggle", summary="启用/禁用技能")
def toggle_skill(skill_id: int, body: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required_enabled)):
    s = SkillService.get_skill(db, skill_id)
    if not s:
        raise ErrNotFound("技能不存在")
    if s.is_builtin:
        raise ErrForbidden("内置技能不可禁用")
    ensure_owner_or_admin(current_user, s.created_by, "技能")
    s.is_active = bool(body.get("is_active", not s.is_active))
    db.commit(); db.refresh(s)
    return ok(_out(s), msg=f"已{'启用' if s.is_active else '禁用'}")
