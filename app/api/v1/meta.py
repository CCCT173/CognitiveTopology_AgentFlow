"""前端元信息接口: 返回可用 provider/loader/splitter/architecture/tool 列表
+ MetaRunner 自然语言操控平台
"""
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.schemas.common import ok
from app.core.config import settings
from app.api.deps import get_db
from app.core.security import get_current_user
from app.services.loaders import list_available as list_loaders
from app.tools import get_registry
from app.models.user import User

router = APIRouter(prefix="/meta", tags=["元信息"])


# ============ Meta Chat: 自然语言操控平台 ============

class MetaChatIn(BaseModel):
    message: str
    thread_id: str | None = None
    history: list[dict] = []


class MetaChatOut(BaseModel):
    reply: str
    tool_calls: list[dict] = []
    steps: list[dict] = []
    pending_confirmations: list[dict] = []


@router.post("/chat", summary="AI 助手（自然语言操控平台）")
def meta_chat(body: MetaChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """与 agentflow AI 助手对话，可以用自然语言：
    - 列出/创建/修改/发布工作流
    - 执行 Python 代码、联网搜索、计算器
    - 查询知识库、管理 Agent

    高危操作（如删除工作流）会返回 pending_confirmations，前端弹窗确认后
    调用 POST /api/v1/hitl/{id}/confirm 真正执行。
    """
    from app.services.meta_runner import build_meta_context, MetaRunner
    runner = MetaRunner()
    ctx = build_meta_context(
        message=body.message,
        db=db,
        user_id=user.user_id,
        history=body.history,
        thread_id=body.thread_id or f"meta-{user.user_id}",
    )
    result = runner.run(ctx)
    out = MetaChatOut(
        reply=result.reply,
        tool_calls=[
            {"tool": c.get("tool"), "args": c.get("args", {})}
            for s in getattr(result, "steps", []) for c in s.get("tool_calls", [])
        ],
        steps=result.steps,
        pending_confirmations=getattr(result, "pending_confirmations", []),
    )
    return ok(out.model_dump())


@router.post("/chat/stream", summary="AI 助手流式（SSE）")
def meta_chat_stream(body: MetaChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """SSE 流式端点，事件类型：
    - iter_start {iter}     新一轮开始
    - thinking {delta}      思考内容
    - delta {delta}         回复文本增量
    - tool {tool,args,result,iter} 工具调用
    - step {iter,tool_calls} 一轮结束
    - done {reply,thinking,tool_calls,steps,pending_confirmations} 最终结果
    - error {msg}           错误
    前端通过 EventSource('...') 或 fetch + ReadableStream 消费。
    """
    from app.services.meta_runner import build_meta_context, MetaRunner
    runner = MetaRunner()
    ctx = build_meta_context(
        message=body.message,
        db=db,
        user_id=user.user_id,
        history=body.history,
        thread_id=body.thread_id or f"meta-{user.user_id}",
    )

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            gen = runner.run_stream(ctx)
            DONE = object()
            cancelled = False
            def _next():
                try:
                    return next(gen)
                except StopIteration:
                    return DONE
            while True:
                # 检测客户端断开（TestClient 下 is_disconnected() 不可靠，try/except 兜底）
                try:
                    disconnected = await request.is_disconnected()
                except Exception:
                    disconnected = False
                if disconnected:
                    cancelled = True
                    break
                ev = await loop.run_in_executor(None, _next)
                if ev is DONE:
                    break
                data = json.dumps(ev, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
            if cancelled:
                yield f"data: {json.dumps({'type': 'cancelled', 'data': {'reason': 'client disconnected'}})}\n\n"
        except Exception as e:
            err = json.dumps({"type": "error", "data": {"msg": f"{type(e).__name__}: {e}"}}, ensure_ascii=False)
            yield f"data: {err}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/providers", summary="可用 LLM/Embedding 提供方")
def providers():
    return ok({
        "llm": {
            "current": settings.LLM_PROVIDER,
            "available": ["giteeai", "ark", "deepseek"],
            "models": {
                "giteeai": settings.GITEEAI_CHAT_MODEL,
                "ark": settings.ARK_CHAT_MODEL,
                "deepseek": settings.DEEPSEEK_MODEL,
            },
        },
        "embedding": {
            "current": settings.EMBEDDING_PROVIDER,
            "available": ["ark", "giteeai", "fake"],
            "model": settings.ARK_EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER == "ark" else settings.EMBEDDING_MODEL_NAME,
            "dim": settings.EMBEDDING_DIM,
        },
    })


@router.get("/loaders", summary="可用文档加载器")
def loaders():
    return ok(list_loaders())


@router.get("/splitters", summary="可用分块方式")
def splitters():
    return ok([
        {"key": "token", "label": "按字符/token"},
        {"key": "sentence", "label": "按句子/标点"},
        {"key": "regex", "label": "按正则表达式"},
        {"key": "semantic", "label": "语义分段"},
    ])


@router.get("/architectures", summary="可用 Agent 架构")
def architectures():
    """Agent architecture 选项。
    设计原则: Agent=执行者, Workflow=编排者, 不重复造轮子"""
    return ok([
        {
            "key": "single",
            "label": "单 Agent",
            "desc": "一次 LLM 调用,可选工具调用。适合简单问答/RAG",
            "needs_framework": False,
        },
        {
            "key": "react",
            "label": "ReAct",
            "desc": "思考-行动-观察循环。适合需要反复查工具/联网场景",
            "needs_framework": False,
        },
        {
            "key": "workflow",
            "label": "工作流封装",
            "desc": "由 Workflow 编排执行,适合企业流程/多分支/人工介入/多Agent协作",
            "needs_framework": True,
            "frameworks": ["", "langgraph", "crewai", "autogen"],
        },
        {
            "key": "skill",
            "label": "Skill 代理",
            "desc": "代理一个 Skill 脚本(见🧩技能页),被其他 Agent/Workflow 作为工具调用,本身不直接面向用户对话",
            "needs_framework": False,
        },
    ])


@router.get("/frameworks", summary="可用底层框架(仅 workflow 架构)")
def frameworks():
    return ok([
        {"key": "",          "label": "内置图执行"},
        {"key": "langgraph", "label": "LangGraph"},
        {"key": "crewai",    "label": "CrewAI"},
        {"key": "autogen",   "label": "AutoGen"},
    ])


@router.get("/tools", summary="可用工具列表")
def tools():
    reg = get_registry()
    return ok([
        {
            "name": t.name,
            "display_name": t.display_name,
            "description": t.description,
            "params_schema": t.params_schema,
        }
        for t in reg.list()
    ])


@router.get("/config", summary="公开的前端配置")
def public_config():
    return ok({
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "password_min_len": settings.PASSWORD_MIN_LEN,
    })


# ============ LLM 参数配置 ============

class LLMConfigOut(BaseModel):
    """LLM 参数配置响应模型"""
    system_prompt: str
    max_context_length: int
    max_output_tokens: int
    thinking_level: int
    is_multimodal_input: bool
    is_embedding_model: bool
    temperature: float
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    response_timeout: int
    api_retry_count: int


class LLMConfigIn(BaseModel):
    """LLM 参数配置更新请求模型"""
    system_prompt: str | None = None
    max_context_length: int | None = None
    max_output_tokens: int | None = None
    thinking_level: int | None = None
    is_multimodal_input: bool | None = None
    is_embedding_model: bool | None = None
    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    response_timeout: int | None = None
    api_retry_count: int | None = None


@router.get("/llm-config", summary="获取 LLM 参数配置")
def get_llm_config(user: User = Depends(get_current_user)):
    """获取当前系统的 LLM 参数配置"""
    return ok({
        "system_prompt": settings.LLM_SYSTEM_PROMPT,
        "max_context_length": settings.LLM_MAX_CONTEXT_LENGTH,
        "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        "thinking_level": settings.LLM_THINKING_LEVEL,
        "is_multimodal_input": settings.LLM_IS_MULTIMODAL_INPUT,
        "is_embedding_model": settings.LLM_IS_EMBEDDING_MODEL,
        "temperature": settings.LLM_TEMPERATURE,
        "top_p": settings.LLM_TOP_P,
        "frequency_penalty": settings.LLM_FREQUENCY_PENALTY,
        "presence_penalty": settings.LLM_PRESENCE_PENALTY,
        "response_timeout": settings.LLM_RESPONSE_TIMEOUT,
        "api_retry_count": settings.LLM_API_RETRY_COUNT,
    })


@router.patch("/llm-config", summary="更新 LLM 参数配置")
def update_llm_config(body: LLMConfigIn, user: User = Depends(get_current_user)):
    """更新 LLM 参数配置（仅更新传入的字段）"""
    import os
    
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return ok({"message": "配置文件不存在"})
    
    content = env_path.read_text(encoding="utf-8")
    
    # 映射字段到环境变量名
    field_mapping = {
        "system_prompt": "LLM_SYSTEM_PROMPT",
        "max_context_length": "LLM_MAX_CONTEXT_LENGTH",
        "max_output_tokens": "LLM_MAX_OUTPUT_TOKENS",
        "thinking_level": "LLM_THINKING_LEVEL",
        "is_multimodal_input": "LLM_IS_MULTIMODAL_INPUT",
        "is_embedding_model": "LLM_IS_EMBEDDING_MODEL",
        "temperature": "LLM_TEMPERATURE",
        "top_p": "LLM_TOP_P",
        "frequency_penalty": "LLM_FREQUENCY_PENALTY",
        "presence_penalty": "LLM_PRESENCE_PENALTY",
        "response_timeout": "LLM_RESPONSE_TIMEOUT",
        "api_retry_count": "LLM_API_RETRY_COUNT",
    }
    
    import re
    updated_fields = []
    
    for field, env_var in field_mapping.items():
        value = getattr(body, field)
        if value is not None:
            # 转换布尔值为字符串
            if isinstance(value, bool):
                value_str = "true" if value else "false"
            else:
                value_str = str(value)
            
            # 替换或添加环境变量
            pattern = rf'^{env_var}=.*$'
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, f'{env_var}={value_str}', content, flags=re.MULTILINE)
            else:
                content += f'\n{env_var}={value_str}'
            
            updated_fields.append(field)
    
    env_path.write_text(content, encoding="utf-8")
    
    return ok({
        "message": f"成功更新 {len(updated_fields)} 个配置项",
        "updated_fields": updated_fields,
        "note": "部分配置需要重启应用才能生效",
    })
