"""
Agent 模板: 预置常用 Agent 配置, 用户可一键克隆到自己的 Agent 列表
- GET /api/v1/agents/templates       返回模板列表
- POST /api/v1/agents/from-template 从模板创建 Agent
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.core.exceptions import ErrNotFound
from app.models.user import User
from app.schemas.common import ok
from app.schemas.agent import AgentOut, AgentCreate
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["Agent模板"])


# ===== 预置 Agent 模板 =====
AGENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "general_assistant",
        "name": "general_assistant",
        "display_name": "通用助手",
        "description": "全能型助手，回答问题、写作、解释概念、头脑风暴",
        "category": "通用",
        "icon": "💡",
        "config": {
            "architecture": "react",
            "system_prompt": "你是一个友好、专业的通用 AI 助手。回答问题清晰、准确、有条理。",
            "description": "全能型 AI 助手",
            "tools": [],
            "llm_config": {"temperature": 0.7, "max_tokens": 2048},
        },
    },
    {
        "id": "code_assistant",
        "name": "code_assistant",
        "display_name": "编程助手",
        "description": "代码编写、调试、解释、重构，支持多种语言",
        "category": "开发",
        "icon": "💻",
        "config": {
            "architecture": "react",
            "system_prompt": "你是一名资深软件工程师。编写代码时遵循最佳实践，给出清晰的注释和解释。代码使用 Markdown 代码块并标注语言。遇到问题先分析根因，再给出修复方案。",
            "description": "专业编程助手",
            "tools": [],
            "llm_config": {"temperature": 0.3, "max_tokens": 4096},
        },
    },
    {
        "id": "translator",
        "name": "translator",
        "display_name": "翻译专家",
        "description": "多语言翻译，支持中英日韩法德等主流语言互译",
        "category": "语言",
        "icon": "🌐",
        "config": {
            "architecture": "single",
            "system_prompt": "你是专业翻译专家。将用户输入翻译成中文（如果原文是中文则翻译成英文）。保持原文语义、语气和风格，专业术语准确，译文自然流畅。只输出译文，不要附加解释。",
            "description": "多语言翻译专家",
            "tools": [],
            "llm_config": {"temperature": 0.3, "max_tokens": 2048},
        },
    },
    {
        "id": "writer",
        "name": "writer",
        "display_name": "文案写作",
        "description": "营销文案、文章、公众号、邮件、简历等各类写作",
        "category": "创作",
        "icon": "✍️",
        "config": {
            "architecture": "react",
            "system_prompt": "你是资深文案与内容创作专家。擅长营销文案、公众号文章、邮件、简历、产品描述等各类文体。文笔生动，结构清晰，能根据受众和场景调整语气风格。",
            "description": "专业文案写作助手",
            "tools": [],
            "llm_config": {"temperature": 0.8, "max_tokens": 4096},
        },
    },
    {
        "id": "rag_expert",
        "name": "rag_expert",
        "display_name": "知识库问答专家",
        "description": "绑定知识库，基于上传文档进行准确问答（需先创建知识库并上传文档）",
        "category": "RAG",
        "icon": "📚",
        "config": {
            "architecture": "rag",
            "system_prompt": "你是知识库问答专家。优先依据检索到的上下文资料回答问题，回答时引用相关片段。如果资料中没有答案，明确告知用户不要臆造。",
            "description": "基于知识库的 RAG 问答专家",
            "tools": ["rag_search"],
            "kb_ids": [],
            "llm_config": {"temperature": 0.2, "max_tokens": 2048},
        },
    },
    {
        "id": "data_analyst",
        "name": "data_analyst",
        "display_name": "数据分析师",
        "description": "数据分析、SQL编写、图表建议、商业洞察",
        "category": "分析",
        "icon": "📊",
        "config": {
            "architecture": "react",
            "system_prompt": "你是数据分析师。擅长 SQL、统计分析、数据可视化建议和业务洞察。回答结构化、数据驱动，必要时给出表格或示例 SQL。",
            "description": "专业数据分析助手",
            "tools": [],
            "llm_config": {"temperature": 0.2, "max_tokens": 4096},
        },
    },
    {
        "id": "product_manager",
        "name": "product_manager",
        "display_name": "产品经理",
        "description": "需求分析、PRD 撰写、竞品分析、用户故事、产品设计",
        "category": "产品",
        "icon": "📱",
        "config": {
            "architecture": "react",
            "system_prompt": "你是资深互联网产品经理。擅长需求梳理、PRD 撰写、用户故事、竞品分析、产品规划。思考用户场景、业务价值和技术可行性，输出结构化方案。",
            "description": "AI 产品经理助手",
            "tools": [],
            "llm_config": {"temperature": 0.6, "max_tokens": 4096},
        },
    },
    {
        "id": "interviewer",
        "name": "interviewer",
        "display_name": "面试官",
        "description": "技术/行为面试模拟，给出反馈和改进建议",
        "category": "学习",
        "icon": "🎯",
        "config": {
            "architecture": "react",
            "system_prompt": "你是资深面试官。根据岗位要求进行模拟面试，一次只问一个问题，根据回答给出专业点评和改进建议。问题由浅入深，既考察基础也考察实战经验。",
            "description": "AI 模拟面试官",
            "tools": [],
            "llm_config": {"temperature": 0.5, "max_tokens": 2048},
        },
    },
]


@router.get("/templates", summary="获取Agent模板列表")
def list_agent_templates(_: User = Depends(get_current_user)):
    return ok([
        {
            "id": t["id"],
            "name": t["name"],
            "display_name": t["display_name"],
            "description": t["description"],
            "category": t["category"],
            "icon": t["icon"],
        }
        for t in AGENT_TEMPLATES
    ])


class FromTemplateIn(BaseModel):
    template_id: str
    name: str | None = None
    display_name: str | None = None


@router.post("/from-template", summary="从模板创建Agent")
def create_from_template(
    body: FromTemplateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tpl = next((t for t in AGENT_TEMPLATES if t["id"] == body.template_id), None)
    if not tpl:
        raise ErrNotFound("模板不存在")
    import uuid
    suffix = uuid.uuid4().hex[:6]
    cfg = tpl["config"]
    payload = AgentCreate(
        name=body.name or f"{tpl['name']}_{suffix}",
        display_name=body.display_name or tpl["display_name"],
        description=cfg.get("description", tpl["description"]),
        architecture=cfg.get("architecture", "single"),
        system_prompt=cfg.get("system_prompt", ""),
        tools=cfg.get("tools", []),
        kb_ids=cfg.get("kb_ids", []),
        llm_config=cfg.get("llm_config", {}),
    )
    obj = agent_service.create_agent(db, payload, user_id=user.user_id)
    return ok(AgentOut.model_validate(obj).model_dump(), msg=f"已从模板「{tpl['display_name']}」创建")
