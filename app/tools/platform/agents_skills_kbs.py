"""
L2 Platform Tools - Agent / Skill / KnowledgeBase 管理工具
让 AI (MetaRunner) 能查询/创建/修改/启停 Agent、管理 Skill、查询知识库。
"""
from __future__ import annotations
from typing import Any
from app.tools import BaseTool, ToolResult, TOOL_TYPE_PLATFORM
from app.db.session import SessionLocal
from app.services.versioning import log_activity
import json


def _ctx_user_id(ctx) -> int:
    if ctx is None:
        return 0
    return getattr(ctx, "user_id", 0) or 0


def _summary_agent(a) -> dict:
    return {
        "name": a.name, "description": a.description or "",
        "model": getattr(a, "model", ""), "enabled": bool(getattr(a, "enabled", True)),
        "architecture": getattr(a, "architecture", "react"),
        "tools": getattr(a, "tools", "") or "",
    }


def _summary_skill(s) -> dict:
    return {
        "id": s.id, "name": s.name, "description": s.description or "",
        "category": s.category or "", "version": getattr(s, "version", 1),
        "is_active": bool(getattr(s, "is_active", True)),
        "is_builtin": bool(getattr(s, "is_builtin", False)),
    }


def _summary_kb(k) -> dict:
    return {
        "id": k.id, "name": k.name, "description": k.description or "",
        "embedding_model": getattr(k, "embedding_model", ""),
        "chunk_size": getattr(k, "chunk_size", 0),
    }


def _get_admin_user(db):
    """获取/创建 admin 用户兜底"""
    from app.models.user import User
    from sqlalchemy import select, func
    from app.core.security import hash_password
    admin = db.scalar(select(User).where(User.account == "admin"))
    if not admin:
        next_uid = db.scalar(select(func.coalesce(func.max(User.user_id), 0))) + 1
        admin = User(
            user_id=next_uid, username="admin", account="admin", email="admin@local",
            password_hash=hash_password("admin123"), role="super_admin",
        )
        db.add(admin); db.commit(); db.refresh(admin)
    return admin


# ============ Agents ============

class ListAgentsTool(BaseTool):
    name = "list_agents"
    display_name = "列出 Agent"
    tool_type = TOOL_TYPE_PLATFORM
    description = "列出所有 Agent（name/description/model/enabled）。可按关键字搜索。"
    params_schema = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "按名称/描述搜索（可选）"},
            "enabled_only": {"type": "boolean", "description": "只返回已启用的"},
        },
    }
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        db = SessionLocal()
        try:
            items = agent_service.list_agents(
                db, keyword=kw.get("keyword"),
                enabled_only=bool(kw.get("enabled_only", False)),
            )
            return ToolResult(ok=True, output=json.dumps([_summary_agent(a) for a in items], ensure_ascii=False, indent=2),
                              data={"count": len(items)})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class GetAgentTool(BaseTool):
    name = "get_agent"
    display_name = "获取 Agent 详情"
    tool_type = TOOL_TYPE_PLATFORM
    description = "按名称获取 Agent 完整配置（system_prompt/model/tools/rag_kb_ids 等）。"
    params_schema = {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Agent 名称"}},
        "required": ["name"],
    }
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        db = SessionLocal()
        try:
            a = agent_service.get_agent(db, kw["name"])
            if not a:
                return ToolResult(ok=False, error=f"Agent '{kw['name']}' 不存在")
            data = _summary_agent(a)
            data["system_prompt"] = getattr(a, "system_prompt", "")
            data["temperature"] = getattr(a, "temperature", 0.7)
            data["max_iterations"] = getattr(a, "max_iterations", 10)
            data["rag_kb_ids"] = getattr(a, "rag_kb_ids", None) or []
            return ToolResult(ok=True, output=json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class ToggleAgentTool(BaseTool):
    name = "toggle_agent"
    display_name = "启用/停用 Agent"
    tool_type = TOOL_TYPE_PLATFORM
    description = "启用或停用 Agent。启用后可被对话和工作流使用。"
    params_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "enabled": {"type": "boolean", "description": "true=启用, false=停用"},
        },
        "required": ["name", "enabled"],
    }
    requires_confirmation = True
    risk_level = "medium"
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        db = SessionLocal()
        try:
            a = agent_service.toggle_agent(db, kw["name"], bool(kw["enabled"]))
            log_activity(db, "agent", a.id, "toggle", user_id=_ctx_user_id(ctx),
                         after={"enabled": bool(kw["enabled"])}, meta={"via": "meta_tool"})
            db.commit()
            return ToolResult(ok=True, output=f"Agent '{a.name}' 已{'启用' if kw['enabled'] else '停用'}")
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


# ============ Skills ============

class ListSkillsTool(BaseTool):
    name = "list_skills"
    display_name = "列出技能"
    tool_type = TOOL_TYPE_PLATFORM
    description = "列出技能（id/name/description/category/version/active）。可按分类/关键字过滤。"
    params_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "keyword": {"type": "string"},
            "active_only": {"type": "boolean"},
        },
    }
    def run(self, ctx=None, **kw):
        from app.services.skill_service import SkillService
        db = SessionLocal()
        try:
            items, _ = SkillService.list_skills(
                db, category=kw.get("category"), keyword=kw.get("keyword"),
                is_active=kw.get("active_only"), limit=100,
            )
            return ToolResult(ok=True, output=json.dumps([_summary_skill(s) for s in items], ensure_ascii=False, indent=2),
                              data={"count": len(items)})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class ToggleSkillTool(BaseTool):
    name = "toggle_skill"
    display_name = "启用/停用技能"
    tool_type = TOOL_TYPE_PLATFORM
    description = "启用或停用某个技能（按 id）。"
    params_schema = {
        "type": "object",
        "properties": {
            "skill_id": {"type": "integer"},
            "active": {"type": "boolean"},
        },
        "required": ["skill_id", "active"],
    }
    requires_confirmation = True
    risk_level = "medium"
    def run(self, ctx=None, **kw):
        from app.services.skill_service import SkillService
        from app.schemas.skill import SkillUpdate
        db = SessionLocal()
        try:
            skill = SkillService.get_skill(db, int(kw["skill_id"]))
            if not skill:
                return ToolResult(ok=False, error=f"技能 {kw['skill_id']} 不存在")
            SkillService.update_skill(db, skill, SkillUpdate(is_active=bool(kw["active"])))
            log_activity(db, "skill", skill.id, "toggle", user_id=_ctx_user_id(ctx),
                         after={"is_active": bool(kw["active"])}, meta={"via": "meta_tool"})
            db.commit()
            return ToolResult(ok=True, output=f"技能 {skill.name} ({skill.id}) 已{'启用' if kw['active'] else '停用'}")
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


# ============ Knowledge Bases ============

class ListKnowledgeBasesTool(BaseTool):
    name = "list_knowledge_bases"
    display_name = "列出知识库"
    tool_type = TOOL_TYPE_PLATFORM
    description = "列出所有知识库（id/name/description/chunk_size）。"
    params_schema = {"type": "object", "properties": {}}
    def run(self, ctx=None, **kw):
        from app.services import rag_service
        db = SessionLocal()
        try:
            items = rag_service.list_kbs(db)
            return ToolResult(ok=True, output=json.dumps([_summary_kb(k) for k in items], ensure_ascii=False, indent=2),
                              data={"count": len(items)})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class KBStatsTool(BaseTool):
    name = "kb_stats"
    display_name = "知识库统计"
    tool_type = TOOL_TYPE_PLATFORM
    description = "查询知识库统计（文档数/向量数/大小）。"
    params_schema = {
        "type": "object",
        "properties": {"kb_id": {"type": "integer"}},
        "required": ["kb_id"],
    }
    def run(self, ctx=None, **kw):
        from app.services import rag_service
        db = SessionLocal()
        try:
            stats = rag_service.kb_stats(db, int(kw["kb_id"]))
            return ToolResult(ok=True, output=json.dumps(stats, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


# ============ Agent create/update/delete ============

class CreateAgentTool(BaseTool):
    name = "create_agent"
    display_name = "创建 Agent"
    tool_type = TOOL_TYPE_PLATFORM
    description = (
        "创建新 Agent。name 是英文唯一标识，system_prompt 是系统提示词，tools 是可用工具名列表，"
        "architecture 可选 react/single/workflow/skill，max_iterations 默认 10。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "英文唯一标识（必填）"},
            "display_name": {"type": "string"},
            "description": {"type": "string"},
            "system_prompt": {"type": "string"},
            "architecture": {"type": "string", "description": "single/react/workflow/skill"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "rag_kb_ids": {"type": "array", "items": {"type": "integer"}},
            "max_iterations": {"type": "integer"},
        },
        "required": ["name"],
    }
    risk_level = "high"
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        from app.schemas.agent import AgentCreate
        db = SessionLocal()
        try:
            data = {
                "name": kw["name"],
                "display_name": kw.get("display_name", kw["name"]),
                "description": kw.get("description", ""),
                "system_prompt": kw.get("system_prompt", ""),
                "architecture": kw.get("architecture", "react"),
                "tools": kw.get("tools", []),
                "rag_kb_ids": kw.get("rag_kb_ids", []),
                "max_iterations": int(kw.get("max_iterations", 10)),
            }
            body = AgentCreate(**data)
            uid = _ctx_user_id(ctx) or None
            a = agent_service.create_agent(db, body, user_id=uid)
            log_activity(db, "agent", a.id, "create", user_id=_ctx_user_id(ctx),
                         after=_summary_agent(a), meta={"via": "meta_tool"})
            # 自动给创建者 owner 权限（对 agent 暂无权限表，activity_log 记录即可）
            db.commit()
            return ToolResult(ok=True, output=json.dumps(_summary_agent(a), ensure_ascii=False, indent=2),
                              data={"agent_name": a.name})
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class UpdateAgentTool(BaseTool):
    name = "update_agent"
    display_name = "更新 Agent"
    tool_type = TOOL_TYPE_PLATFORM
    description = "更新 Agent 的 system_prompt/description/tools 等字段。只传要修改的字段。"
    params_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Agent 名称（必填）"},
            "display_name": {"type": "string"},
            "description": {"type": "string"},
            "system_prompt": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "rag_kb_ids": {"type": "array", "items": {"type": "integer"}},
            "max_iterations": {"type": "integer"},
        },
        "required": ["name"],
    }
    risk_level = "high"
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        from app.schemas.agent import AgentUpdate
        db = SessionLocal()
        try:
            data = {}
            for field in ("display_name", "description", "system_prompt", "tools",
                          "rag_kb_ids", "max_iterations", "architecture"):
                if field in kw and kw[field] is not None:
                    data[field] = kw[field]
            body = AgentUpdate(**data)
            a = agent_service.update_agent(db, kw["name"], body)
            log_activity(db, "agent", a.id, "update", user_id=_ctx_user_id(ctx),
                         after=_summary_agent(a), meta={"via": "meta_tool", "fields": list(data.keys())})
            db.commit()
            return ToolResult(ok=True, output=json.dumps(_summary_agent(a), ensure_ascii=False, indent=2))
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class DeleteAgentTool(BaseTool):
    name = "delete_agent"
    display_name = "删除 Agent"
    tool_type = TOOL_TYPE_PLATFORM
    description = "删除 Agent（不可恢复）。"
    params_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    requires_confirmation = True
    risk_level = "critical"
    def run(self, ctx=None, **kw):
        from app.services import agent_service
        db = SessionLocal()
        try:
            name = kw["name"]
            a = agent_service.get_agent(db, name)
            if not a:
                return ToolResult(ok=False, error=f"Agent '{name}' 不存在")
            before = _summary_agent(a)
            agent_service.delete_agent(db, name)
            log_activity(db, "agent", a.id, "delete", user_id=_ctx_user_id(ctx),
                         before=before, meta={"via": "meta_tool"})
            db.commit()
            return ToolResult(ok=True, output=f"已删除 Agent '{name}'")
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


# ============ KB create/delete ============

class CreateKnowledgeBaseTool(BaseTool):
    name = "create_knowledge_base"
    display_name = "创建知识库"
    tool_type = TOOL_TYPE_PLATFORM
    description = "创建新知识库。name 必填，chunk_size 默认 500，chunk_overlap 默认 50。"
    params_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string"},
            "embedding_model": {"type": "string"},
            "chunk_size": {"type": "integer"},
            "chunk_overlap": {"type": "integer"},
        },
        "required": ["name"],
    }
    risk_level = "high"
    def run(self, ctx=None, **kw):
        from app.services import rag_service
        from app.schemas.rag import KBCreate
        db = SessionLocal()
        try:
            body = KBCreate(
                name=kw["name"],
                description=kw.get("description", ""),
                category=kw.get("category", ""),
                embedding_model=kw.get("embedding_model", ""),
                chunk_size=int(kw.get("chunk_size", 500)),
                chunk_overlap=int(kw.get("chunk_overlap", 50)),
            )
            uid = _ctx_user_id(ctx) or None
            kb = rag_service.create_kb(db, body, user_id=uid)
            db.commit()
            return ToolResult(ok=True, output=json.dumps(_summary_kb(kb), ensure_ascii=False, indent=2),
                              data={"kb_id": kb.id})
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class DeleteKnowledgeBaseTool(BaseTool):
    name = "delete_knowledge_base"
    display_name = "删除知识库"
    tool_type = TOOL_TYPE_PLATFORM
    description = "删除知识库及其所有文档（不可恢复）。"
    params_schema = {
        "type": "object",
        "properties": {"kb_id": {"type": "integer"}},
        "required": ["kb_id"],
    }
    requires_confirmation = True
    risk_level = "critical"
    def run(self, ctx=None, **kw):
        from app.services import rag_service
        db = SessionLocal()
        try:
            kb_id = int(kw["kb_id"])
            kb = rag_service.get_kb(db, kb_id)
            if not kb:
                return ToolResult(ok=False, error=f"知识库 {kb_id} 不存在")
            before = _summary_kb(kb)
            rag_service.delete_kb(db, kb_id)
            db.commit()
            return ToolResult(ok=True, output=f"已删除知识库 #{kb_id}（{before['name']}）")
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


def register_all():
    from app.tools import registry
    for cls in (ListAgentsTool, GetAgentTool, ToggleAgentTool,
                ListSkillsTool, ToggleSkillTool,
                ListKnowledgeBasesTool, KBStatsTool,
                CreateAgentTool, UpdateAgentTool, DeleteAgentTool,
                CreateKnowledgeBaseTool, DeleteKnowledgeBaseTool):
        registry.register(cls())
        registry.register(cls())
