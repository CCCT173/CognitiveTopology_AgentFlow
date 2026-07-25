"""
Agent CRUD + 运行时管理骨架
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models.agent import Agent as AgentModel
from app.schemas.agent import AgentCreate, AgentUpdate, _merge_llm_config
from app.core.exceptions import ErrNotFound, ErrConflict


def list_agents(db: Session, keyword: Optional[str] = None, enabled_only: bool = False,
                owner_id: int | None = None, include_public: bool = False) -> list[AgentModel]:
    """
    列出 Agent:
    - owner_id=None: 全部(管理员使用)
    - owner_id=<uid>: 指定 owner; 若 include_public=True, 同时返回 enabled 的公开 Agent
    """
    stmt = select(AgentModel)
    if keyword:
        stmt = stmt.where(AgentModel.name.ilike(f"%{keyword}%"))
    if enabled_only:
        stmt = stmt.where(AgentModel.enabled.is_(True))
    if owner_id is not None:
        if include_public:
            stmt = stmt.where(or_(AgentModel.created_by == owner_id, AgentModel.enabled.is_(True)))
        else:
            stmt = stmt.where(AgentModel.created_by == owner_id)
    return list(db.scalars(stmt).all())


def get_agent(db: Session, name: str) -> AgentModel:
    obj = db.scalar(select(AgentModel).where(AgentModel.name == name))
    if not obj:
        raise ErrNotFound(f"Agent '{name}' 不存在")
    return obj


def create_agent(db: Session, body: AgentCreate, user_id: int | None = None) -> AgentModel:
    if db.scalar(select(AgentModel).where(AgentModel.name == body.name)):
        raise ErrConflict(f"Agent '{body.name}' 已存在")
    data = body.model_dump()
    # 创建时合并 llm_config 默认值,保证缺失字段也有默认
    data["llm_config"] = _merge_llm_config(data.get("llm_config"))
    obj = AgentModel(**data, created_by=user_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_agent(db: Session, name: str, body: AgentUpdate) -> AgentModel:
    obj = get_agent(db, name)
    updates = body.model_dump(exclude_unset=True)
    # 如果显式更新 llm_config, 与现有合并(避免丢失之前设置的字段)
    if "llm_config" in updates and updates["llm_config"] is not None:
        merged = dict(obj.llm_config or {})
        merged.update(updates["llm_config"])
        updates["llm_config"] = merged
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_agent(db: Session, name: str) -> None:
    obj = get_agent(db, name)
    db.delete(obj)
    db.commit()


def toggle_agent(db: Session, name: str, enabled: bool) -> AgentModel:
    obj = get_agent(db, name)
    obj.enabled = enabled
    db.commit()
    db.refresh(obj)
    return obj
