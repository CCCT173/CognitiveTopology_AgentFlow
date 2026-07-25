"""v1 路由聚合"""
from fastapi import APIRouter, Depends

from app.api.v1 import auth, users, agents, chat, rag, groups, workflows, meta, skills, system, workflow_templates, agent_templates, hitl, workflow_permissions, workflow_api_keys, db_connections
from app.core.security import get_current_user

api_router = APIRouter(prefix="/api/v1")

# 公开接口(不需登录)
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(system.router)  # /system/status 公开,其他接口已在内部加权限
# 外部调用端点：/api/v1/execute/{key} 用 API Key 认证，无 JWT
api_router.include_router(workflow_api_keys.exec_router)

# 以下接口默认要求登录
_protected = APIRouter(dependencies=[Depends(get_current_user)])
_protected.include_router(users.router)
_protected.include_router(agent_templates.router)  # 必须在 agents 之前, 避免 /templates 被 /{name} 截获
_protected.include_router(agents.router)
_protected.include_router(chat.router)
_protected.include_router(rag.router)
_protected.include_router(groups.router)
_protected.include_router(workflow_templates.router)  # 必须在 workflows 之前, 避免 /templates 被 /{wf_id} 截获
_protected.include_router(workflow_api_keys.router)
_protected.include_router(workflows.router)
_protected.include_router(workflow_permissions.router)
_protected.include_router(skills.router)
_protected.include_router(hitl.router)
_protected.include_router(db_connections.router)

api_router.include_router(_protected)
