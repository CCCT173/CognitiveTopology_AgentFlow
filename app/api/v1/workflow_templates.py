"""
工作流模板: 预置常用DAG模板, 用户可一键克隆到自己的工作流
- GET /api/v1/workflows/templates  返回模板列表(预置, 不含数据库)
- POST /api/v1/workflows/from-template 从模板创建工作流
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
from app.schemas.workflow import WorkflowOut
from app.services import workflow_service

router = APIRouter(prefix="/workflows", tags=["工作流模板"])


# ===== 预置模板定义 =====
TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "simple_chat",
        "name": "simple_chat",
        "display_name": "💬 简单对话",
        "description": "开始 → LLM → 结束，最基础的LLM对话流程",
        "category": "基础",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 80, "y": 200}},
                {"id": "llm", "type": "llm", "name": "LLM", "config": {"prompt": "{{input}}", "system_prompt": "你是一个友好的助手。", "temperature": 0.7, "max_tokens": 2048}, "position": {"x": 340, "y": 200}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": "{{llm.text}}"}, "position": {"x": 600, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "llm"},
                {"id": "e2", "source": "llm", "target": "end"},
            ],
            "entry": "start",
        },
    },
    {
        "id": "rag_qa",
        "name": "rag_qa",
        "display_name": "📚 RAG 知识库问答",
        "description": "先检索知识库，再把上下文交给LLM回答",
        "category": "RAG",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 60, "y": 200}},
                {"id": "search", "type": "tool", "name": "知识库检索", "config": {"tool_name": "rag_search", "params": {"query": "{{input}}", "top_k": 5}}, "position": {"x": 300, "y": 200}},
                {"id": "llm", "type": "llm", "name": "LLM", "config": {"prompt": "根据以下资料回答问题：\n\n{{search.result}}\n\n问题：{{input}}\n\n请用中文回答：", "system_prompt": "你是知识库问答助手，只能依据给定资料作答，若资料不足请说明。", "temperature": 0.3}, "position": {"x": 560, "y": 200}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": "{{llm.text}}"}, "position": {"x": 820, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "search"},
                {"id": "e2", "source": "search", "target": "llm"},
                {"id": "e3", "source": "llm", "target": "end"},
            ],
            "entry": "start",
        },
    },
    {
        "id": "branch_logic",
        "name": "branch_logic",
        "display_name": "🔀 智能路由",
        "description": "根据用户意图路由到不同处理：问候/问题/投诉",
        "category": "流程控制",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 60, "y": 240}},
                {"id": "classify", "type": "llm", "name": "意图分类", "config": {"prompt": "用户输入：{{input}}\n\n判断意图，只回复一个词：greeting / question / complaint", "system_prompt": "你是意图分类器，只输出一个标签。", "temperature": 0.0, "max_tokens": 20}, "position": {"x": 300, "y": 240}},
                {"id": "cond", "type": "condition", "name": "判断分支", "config": {"expression": "classify.text.strip()"}, "position": {"x": 540, "y": 240}},
                {"id": "greet", "type": "llm", "name": "问候回复", "config": {"prompt": "用户问候：{{input}}，请友好回应", "temperature": 0.7}, "position": {"x": 780, "y": 80}},
                {"id": "answer", "type": "llm", "name": "问题回答", "config": {"prompt": "{{input}}", "temperature": 0.5}, "position": {"x": 780, "y": 240}},
                {"id": "complain", "type": "llm", "name": "投诉处理", "config": {"prompt": "用户投诉：{{input}}，请专业、安抚地回应", "temperature": 0.3}, "position": {"x": 780, "y": 400}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": ""}, "position": {"x": 1040, "y": 240}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "classify"},
                {"id": "e2", "source": "classify", "target": "cond"},
                {"id": "e3", "source": "cond", "target": "greet", "condition": "greeting"},
                {"id": "e4", "source": "cond", "target": "answer", "condition": "question"},
                {"id": "e5", "source": "cond", "target": "complain", "condition": "complaint"},
                {"id": "e6", "source": "greet", "target": "end"},
                {"id": "e7", "source": "answer", "target": "end"},
                {"id": "e8", "source": "complain", "target": "end"},
            ],
            "entry": "start",
        },
    },
    {
        "id": "translate_review",
        "name": "translate_review",
        "display_name": "🌐 翻译+审校",
        "description": "LLM翻译 → 第二个LLM审校润色 → 输出",
        "category": "内容处理",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 60, "y": 200}},
                {"id": "trans", "type": "llm", "name": "翻译", "config": {"prompt": "将下面文本翻译成中文：\n\n{{input}}", "temperature": 0.3}, "position": {"x": 300, "y": 200}},
                {"id": "review", "type": "llm", "name": "审校润色", "config": {"prompt": "请审校以下翻译，修正错误并润色语言使其更自然：\n\n原文：{{input}}\n\n初译：{{trans.text}}\n\n输出最终中文译文：", "temperature": 0.5}, "position": {"x": 560, "y": 200}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": "{{review.text}}"}, "position": {"x": 820, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "trans"},
                {"id": "e2", "source": "trans", "target": "review"},
                {"id": "e3", "source": "review", "target": "end"},
            ],
            "entry": "start",
        },
    },
    {
        "id": "summarize_extract",
        "name": "summarize_extract",
        "display_name": "📝 摘要+关键词提取",
        "description": "对输入文本生成摘要，并提取关键要点",
        "category": "内容处理",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 60, "y": 200}},
                {"id": "summary", "type": "llm", "name": "生成摘要", "config": {"prompt": "请为以下文本生成一段100字以内的摘要：\n\n{{input}}", "temperature": 0.3}, "position": {"x": 300, "y": 140}},
                {"id": "keywords", "type": "llm", "name": "提取关键词", "config": {"prompt": "请从以下文本中提取5-8个关键词，用逗号分隔：\n\n{{input}}", "temperature": 0.2}, "position": {"x": 300, "y": 300}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": "{\"summary\": \"{{summary.text}}\", \"keywords\": \"{{keywords.text}}\"}"}, "position": {"x": 600, "y": 220}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "summary"},
                {"id": "e2", "source": "start", "target": "keywords"},
                {"id": "e3", "source": "summary", "target": "end"},
                {"id": "e4", "source": "keywords", "target": "end"},
            ],
            "entry": "start",
        },
    },
    {
        "id": "skill_chain",
        "name": "skill_chain",
        "display_name": "🧩 技能链式调用",
        "description": "开始 → Skill A → Skill B → 结束",
        "category": "技能编排",
        "definition": {
            "nodes": [
                {"id": "start", "type": "start", "name": "开始", "config": {}, "position": {"x": 60, "y": 200}},
                {"id": "sk1", "type": "skill", "name": "技能1", "config": {"skill_name": "", "params": {}}, "position": {"x": 320, "y": 200}},
                {"id": "sk2", "type": "skill", "name": "技能2", "config": {"skill_name": "", "params": {}}, "position": {"x": 580, "y": 200}},
                {"id": "end", "type": "end", "name": "结束", "config": {"output_key": "{{sk2.output}}"}, "position": {"x": 840, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "sk1"},
                {"id": "e2", "source": "sk1", "target": "sk2"},
                {"id": "e3", "source": "sk2", "target": "end"},
            ],
            "entry": "start",
        },
    },
]


class FromTemplateIn(BaseModel):
    template_id: str
    name: str | None = None
    display_name: str | None = None


@router.get("/templates", summary="获取工作流模板列表")
def list_templates(_: User = Depends(get_current_user)):
    return ok([
        {
            "id": t["id"],
            "name": t["name"],
            "display_name": t["display_name"],
            "description": t["description"],
            "category": t["category"],
            "node_count": len(t["definition"]["nodes"]),
            "edge_count": len(t["definition"]["edges"]),
        }
        for t in TEMPLATES
    ])


@router.get("/templates/{tpl_id}", summary="获取模板详情")
def get_template(tpl_id: str, _: User = Depends(get_current_user)):
    for t in TEMPLATES:
        if t["id"] == tpl_id:
            return ok(t)
    raise ErrNotFound("模板不存在")


@router.post("/from-template", summary="从模板创建工作流")
def create_from_template(
    body: FromTemplateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tpl = next((t for t in TEMPLATES if t["id"] == body.template_id), None)
    if not tpl:
        raise ErrNotFound("模板不存在")

    from app.schemas.workflow import WorkflowCreate
    import uuid
    suffix = uuid.uuid4().hex[:6]
    wf = workflow_service.create_workflow(db, user, WorkflowCreate(
        name=body.name or f"{tpl['name']}_{suffix}",
        display_name=body.display_name or tpl["display_name"],
        description=tpl["description"],
        category=tpl["category"],
        definition=tpl["definition"],
    ))
    return ok(WorkflowOut.model_validate(wf).model_dump(), msg=f"已从模板「{tpl['display_name']}」创建")
