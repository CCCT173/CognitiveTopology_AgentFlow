"""
版本控制和活动日志服务
- publish_workflow: 创建工作流版本快照
- publish_agent: 创建 Agent 版本快照
- log_activity: 记录活动日志
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.workflow import Workflow
from app.models.agent import Agent
from app.models.versioning import WorkflowVersion, AgentVersion, ActivityLog


def log_activity(db: Session, entity_type: str, entity_id: int, action: str,
                 user_id: int = 0, before: dict | None = None, after: dict | None = None,
                 meta: dict | None = None):
    """记录活动日志"""
    log = ActivityLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        before_json=json.dumps(before or {}, ensure_ascii=False, default=str),
        after_json=json.dumps(after or {}, ensure_ascii=False, default=str),
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(log)
    return log


def publish_workflow(db: Session, workflow: Workflow, user_id: int = 0,
                    changelog: str = "") -> WorkflowVersion:
    """发布工作流：写入 version 快照"""
    next_ver = db.scalar(
        select(func.coalesce(func.max(WorkflowVersion.version), 0))
        .where(WorkflowVersion.workflow_id == workflow.id)
    ) + 1
    wv = WorkflowVersion(
        workflow_id=workflow.id,
        version=next_ver,
        name=workflow.name,
        description=workflow.description or "",
        definition_json=json.dumps(workflow.definition or {}, ensure_ascii=False, default=str),
        changelog=changelog,
        published_by=user_id,
    )
    db.add(wv)
    log_activity(
        db, "workflow", workflow.id, "publish", user_id=user_id,
        before={"version": next_ver - 1}, after={"version": next_ver},
        meta={"name": workflow.name},
    )
    db.flush()
    return wv


def publish_agent(db: Session, agent: Agent, user_id: int = 0,
                 changelog: str = "") -> AgentVersion:
    """发布 Agent"""
    next_ver = db.scalar(
        select(func.coalesce(func.max(AgentVersion.version), 0))
        .where(AgentVersion.agent_id == agent.id)
    ) + 1
    snapshot = {
        "name": agent.name,
        "description": agent.description or "",
        "system_prompt": agent.system_prompt or "",
        "model": agent.model or "",
        "provider": agent.provider or "",
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "tools": list(agent.tools or []),
        "rag_kb_ids": list(agent.rag_kb_ids or []),
        "architecture": agent.architecture or "",
    }
    av = AgentVersion(
        agent_id=agent.id,
        version=next_ver,
        name=agent.name,
        system_prompt=agent.system_prompt or "",
        config_json=json.dumps(snapshot, ensure_ascii=False, default=str),
        changelog=changelog,
        published_by=user_id,
    )
    db.add(av)
    log_activity(
        db, "agent", agent.id, "publish", user_id=user_id,
        before={"version": next_ver - 1}, after={"version": next_ver},
    )
    db.flush()
    return av
