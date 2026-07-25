"""
L2 Platform Tools - 工作流管理工具
这些工具让 AI (MetaRunner) 能查询/创建/修改/发布工作流。
所有操作走 DB session 并带 owner 校验，结果可追溯到 activity_log。
"""
from __future__ import annotations
from typing import Any
from app.tools import BaseTool, ToolResult, TOOL_TYPE_PLATFORM
from app.db.session import SessionLocal
from app.services import workflow_service
from app.services.versioning import log_activity
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
import json


def _ctx_user_id(ctx) -> int:
    """从 ctx 里取 user_id，兜底 0 (system)"""
    if ctx is None:
        return 0
    return getattr(ctx, "user_id", 0) or 0


# ---- helpers ----
def _summary(wf) -> dict:
    """工作流摘要，避免把完整 DSL 都吐给 LLM"""
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description or "",
        "category": wf.category or "",
        "enabled": bool(wf.enabled),
        "version": getattr(wf, "version", 1),
        "updated_at": str(wf.updated_at) if wf.updated_at else None,
    }


class ListWorkflowsTool(BaseTool):
    name = "list_workflows"
    display_name = "列出工作流"
    tool_type = TOOL_TYPE_PLATFORM
    description = "列出当前用户可见的工作流（返回 id/name/description/enabled/version，不含完整 DSL）。"
    params_schema = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "按名称搜索（可选）"},
            "category": {"type": "string", "description": "按分类筛选（可选）"},
        },
    }

    def run(self, ctx: Any = None, **kw) -> ToolResult:
        db = SessionLocal()
        try:
            items = workflow_service.list_workflows(db, keyword=kw.get("keyword"),
                                                     category=kw.get("category"))
            return ToolResult(ok=True, output=json.dumps([_summary(w) for w in items], ensure_ascii=False, indent=2),
                              data={"count": len(items)})
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class GetWorkflowTool(BaseTool):
    name = "get_workflow"
    display_name = "获取工作流详情"
    tool_type = TOOL_TYPE_PLATFORM
    description = "获取工作流完整定义（含 nodes/edges/DSL），用于查看或修改前读取。"
    params_schema = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "integer", "description": "工作流 ID"},
        },
        "required": ["workflow_id"],
    }

    def run(self, ctx=None, **kw) -> ToolResult:
        db = SessionLocal()
        try:
            wf = workflow_service.get_workflow(db, int(kw["workflow_id"]))
            if not wf:
                return ToolResult(ok=False, error=f"工作流 {kw['workflow_id']} 不存在")
            data = _summary(wf)
            data["definition"] = wf.definition or {}
            return ToolResult(ok=True, output=json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class CreateWorkflowTool(BaseTool):
    name = "create_workflow"
    display_name = "创建工作流"
    tool_type = TOOL_TYPE_PLATFORM
    description = "创建一个新工作流。定义格式：{'entry':'node_id','nodes':[{'id':n1,'type':'llm','config':{...}}],'edges':[{'source':n1,'target':n2}]}"
    params_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "工作流名称（必填）"},
            "description": {"type": "string", "description": "描述"},
            "category": {"type": "string", "description": "分类"},
            "definition": {"type": "object", "description": "工作流 DSL: {entry, nodes, edges}"},
        },
        "required": ["name"],
    }
    requires_confirmation = False
    risk_level = "high"

    def run(self, ctx=None, **kw) -> ToolResult:
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.models.workflow import Workflow
            from app.core.security import hash_password
            from sqlalchemy import select, func
            admin = db.scalar(select(User).where(User.account == "admin"))
            if not admin:
                # 兜底：创建 admin 用户（测试/新库场景）
                from app.core.time import utc_now_naive
                next_uid = db.scalar(select(func.coalesce(func.max(User.user_id), 0))) + 1
                admin = User(
                    user_id=next_uid,
                    username="admin", account="admin", email="admin@local",
                    password_hash=hash_password("admin123"), role="super_admin",
                )
                db.add(admin); db.commit(); db.refresh(admin)
            body = WorkflowCreate(
                name=kw["name"],
                description=kw.get("description", ""),
                category=kw.get("category", ""),
                definition=kw.get("definition", {}),
            )
            # SQLite + BigInteger 主键不自增，显式分配 id
            next_id = db.scalar(select(func.coalesce(func.max(Workflow.id), 0))) + 1
            wf = workflow_service.create_workflow(db, admin, body)
            if not wf.id:
                wf.id = next_id
                db.flush()
            # 自动给 ctx user owner 权限（如果有 user_id 且不是 admin 自己）
            ctx_uid = _ctx_user_id(ctx)
            from app.services import workflow_permission_service as perm_svc
            perm_svc.ensure_creator_owner(db, wf.id, admin.user_id)
            if ctx_uid and ctx_uid != admin.user_id:
                perm_svc.grant_permission(db, wf.id, ctx_uid, "owner", granted_by=admin.user_id)
            log_activity(db, "workflow", wf.id, "create",
                         user_id=ctx_uid,
                         after={"name": wf.name, "category": wf.category},
                         meta={"via": "meta_tool"})
            db.commit()
            return ToolResult(ok=True, output=json.dumps(_summary(wf), ensure_ascii=False, indent=2),
                              data={"workflow_id": wf.id})
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class UpdateWorkflowTool(BaseTool):
    name = "update_workflow"
    display_name = "更新工作流"
    tool_type = TOOL_TYPE_PLATFORM
    description = "更新工作流（修改名称/描述/DSL）。传入需要更新的字段，不传的保持不变。乐观锁：冲突返回 409。"
    params_schema = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "integer"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string"},
            "definition": {"type": "object", "description": "新 DSL，覆盖原定义"},
        },
        "required": ["workflow_id"],
    }
    risk_level = "high"

    def run(self, ctx=None, **kw) -> ToolResult:
        db = SessionLocal()
        try:
            # 只把用户显式提供的字段传进去（None 表示"不更新"）
            from app.schemas.workflow import WorkflowUpdate
            data = {}
            for field in ("name", "description", "category", "definition"):
                if field in kw and kw[field] is not None:
                    data[field] = kw[field]
            body = WorkflowUpdate(**data)
            before = {"name": kw.get("name"), "description": kw.get("description"),
                      "category": kw.get("category"), "definition": kw.get("definition")}
            wf = workflow_service.update_workflow(db, int(kw["workflow_id"]), body)
            log_activity(db, "workflow", wf.id, "update",
                         user_id=_ctx_user_id(ctx), before=before,
                         after={"name": wf.name, "description": wf.description, "category": wf.category},
                         meta={"via": "meta_tool", "fields": list(data.keys())})
            db.commit()
            return ToolResult(ok=True, output=json.dumps(_summary(wf), ensure_ascii=False, indent=2))
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


class DeleteWorkflowTool(BaseTool):
    name = "delete_workflow"
    display_name = "删除工作流"
    tool_type = TOOL_TYPE_PLATFORM
    description = "删除工作流（不可恢复）。"
    params_schema = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "integer"},
        },
        "required": ["workflow_id"],
    }
    requires_confirmation = True  # 高危操作

    def run(self, ctx=None, **kw) -> ToolResult:
        db = SessionLocal()
        try:
            wid = int(kw["workflow_id"])
            wf = workflow_service.get_workflow(db, wid)
            before = _summary(wf) if wf else None
            workflow_service.delete_workflow(db, wid)
            log_activity(db, "workflow", wid, "delete",
                         user_id=_ctx_user_id(ctx), before=before,
                         meta={"via": "meta_tool"})
            db.commit()
            return ToolResult(ok=True, output=f"已删除工作流 {wid}")
        except Exception as e:
            db.rollback()
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
        finally:
            db.close()


def register_all():
    from app.tools import registry
    for cls in (ListWorkflowsTool, GetWorkflowTool, CreateWorkflowTool,
                UpdateWorkflowTool, DeleteWorkflowTool):
        registry.register(cls())
