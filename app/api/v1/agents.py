"""
Agent 管理接口
功能概览:
  GET    /api/v1/agents                列出 Agent (admin/super_admin 看全部; 普通用户看自己创建的 + enabled 的公开 Agent)
  POST   /api/v1/agents                创建新 Agent
  GET    /api/v1/agents/{name}         查询 Agent 详情 (owner 或 admin)
  PATCH  /api/v1/agents/{name}         更新 Agent (owner 或 admin)
  DELETE /api/v1/agents/{name}         删除 Agent (owner 或 admin)
  POST   /api/v1/agents/{name}/toggle  启用/禁用 Agent (owner 或 admin)
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, ensure_owner_or_admin, is_admin
from app.core.security import get_current_user_required_enabled
from app.schemas.common import ok
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut, ToggleEnable
from app.services import agent_service
from app.models.user import User

router = APIRouter(prefix="/agents", tags=["Agent管理"])


@router.get("", summary="列出Agent")
def list_agents(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索, 留空返回全部"),
    enabled_only: bool = Query(False, description="true=只返回已启用的Agent"),
    mine: bool = Query(False, description="true=只返回我创建的"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    """
    返回 Agent 列表:
    - admin/super_admin: 默认全部(可加 mine=true 看自己的)
    - 普通 user: 只能看到自己创建的 (mine 参数忽略, 强制过滤)
    """
    if is_admin(user):
        owner_id = user.user_id if mine else None
        data = [AgentOut.model_validate(a).model_dump()
                for a in agent_service.list_agents(db, keyword, enabled_only, owner_id=owner_id, include_public=False)]
    else:
        # 普通用户强制只能看到自己创建的
        data = [AgentOut.model_validate(a).model_dump()
                for a in agent_service.list_agents(db, keyword, enabled_only, owner_id=user.user_id, include_public=False)]
    return ok(data)


@router.post("", summary="创建Agent")
def create_agent(
    body: AgentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    obj = agent_service.create_agent(db, body, user_id=user.user_id)
    return ok(AgentOut.model_validate(obj).model_dump())


def _get_checked(db: Session, name: str, user: User):
    obj = agent_service.get_agent(db, name)
    ensure_owner_or_admin(user, obj.created_by, "Agent")
    return obj


@router.get("/{name}", summary="查询Agent详情/配置")
def get_agent(name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    obj = _get_checked(db, name, user)
    return ok(AgentOut.model_validate(obj).model_dump())


@router.patch("/{name}", summary="更新Agent")
def update_agent(name: str, body: AgentUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user_required_enabled)):
    _get_checked(db, name, user)
    obj = agent_service.update_agent(db, name, body)
    return ok(AgentOut.model_validate(obj).model_dump())


@router.delete("/{name}", summary="删除Agent")
def delete_agent(name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _get_checked(db, name, user)
    agent_service.delete_agent(db, name)
    return ok(msg="已删除")


@router.post("/{name}/toggle", summary="启用/禁用Agent")
def toggle(name: str, body: ToggleEnable, db: Session = Depends(get_db),
           user: User = Depends(get_current_user_required_enabled)):
    _get_checked(db, name, user)
    obj = agent_service.toggle_agent(db, name, body.enabled)
    return ok(AgentOut.model_validate(obj).model_dump())
