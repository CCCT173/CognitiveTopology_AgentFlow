"""Agent 对话服务: 按 agent.architecture dispatch 到对应 Runner"""
import json
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.agent import Agent as AgentModel, AgentChatMessage, ChatThread
from app.schemas.agent import ChatIn
from app.core.exceptions import ErrNotFound, ErrBadRequest, ErrForbidden
from app.services.agent_runtime import get_runner, AgentContext, RunResult
from app.core.logger import logger


def _get_or_create_thread(db: Session, user_id: int, agent_name: str, thread_id: str) -> ChatThread:
    if not thread_id:
        thread = ChatThread(thread_id=uuid.uuid4().hex, user_id=user_id, agent_name=agent_name, title="新对话")
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread
    tid = thread_id
    thread = db.scalar(select(ChatThread).where(ChatThread.thread_id == tid))
    if not thread:
        thread = ChatThread(thread_id=tid, user_id=user_id, agent_name=agent_name, title="新对话")
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread
    if thread.agent_name != agent_name or thread.user_id != user_id:
        raise ErrBadRequest("thread 与 agent/user 不匹配")
    return thread


def _load_history(db: Session, thread_id: str, limit: int = 10) -> list[dict]:
    msgs = db.scalars(
        select(AgentChatMessage)
        .where(AgentChatMessage.thread_id == thread_id)
        .order_by(AgentChatMessage.id.desc()).limit(limit)
    ).all()
    msgs.reverse()
    return [{"role": m.role, "content": m.content} for m in msgs]


def _build_context(db: Session, user_id: int, body: ChatIn):
    agent = db.scalar(select(AgentModel).where(AgentModel.name == body.agent_name))
    if not agent:
        raise ErrNotFound(f"Agent '{body.agent_name}' 不存在")
    if not agent.enabled:
        raise ErrBadRequest(f"Agent '{body.agent_name}' 已禁用")
    if agent.architecture == "skill":
        raise ErrForbidden("Skill 类型 Agent 只能被其他 Agent 作为工具调用,不能直接对话")

    thread = _get_or_create_thread(db, user_id, agent.name, body.thread_id)
    history = _load_history(db, thread.thread_id, limit=10)
    ctx = AgentContext(
        db=db, user_id=user_id, agent=agent,
        message=body.message, thread_id=thread.thread_id,
        variables=body.variables, history=history,
    )
    return agent, thread, ctx


def chat(db: Session, user_id: int, body: ChatIn) -> dict:
    agent, thread, ctx = _build_context(db, user_id, body)
    runner = get_runner(agent.architecture)
    try:
        result: RunResult = runner.run(ctx)
    except Exception as e:
        logger.exception(f"agent run failed: {e}")
        result = RunResult(reply=f"[执行失败: {e}]")

    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="user", content=body.message))
    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="assistant", content=result.reply))
    if thread.title == "新对话":
        thread.title = body.message[:30]
    thread.last_message = result.reply[:200]
    db.commit()

    return {
        "reply": result.reply,
        "thinking": "",
        "thread_id": thread.thread_id,
        "title": thread.title,
        "tool_calls": result.tool_calls,
        "steps": result.steps,
        "citations": result.citations or [],
    }


async def chat_async(db: Session, user_id: int, body: ChatIn) -> dict:
    """异步版本的 chat 函数，使用异步 LLM 客户端"""
    agent, thread, ctx = _build_context(db, user_id, body)
    runner = get_runner(agent.architecture)
    try:
        result: RunResult = await runner.async_run(ctx)
    except Exception as e:
        logger.exception(f"agent run failed: {e}")
        result = RunResult(reply=f"[执行失败: {e}]")

    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="user", content=body.message))
    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="assistant", content=result.reply))
    if thread.title == "新对话":
        thread.title = body.message[:30]
    thread.last_message = result.reply[:200]
    db.commit()

    return {
        "reply": result.reply,
        "thinking": "",
        "thread_id": thread.thread_id,
        "title": thread.title,
        "tool_calls": result.tool_calls,
        "steps": result.steps,
        "citations": result.citations or [],
    }


def chat_stream(db: Session, user_id: int, body: ChatIn):
    """SSE 流式生成器, yield 'data: <json>\\n\\n' 形式, 结束时 yield 'data: [DONE]\\n\\n'"""
    def emit(type_: str, data: dict) -> str:
        return f"data: {json.dumps({'type': type_, **data}, ensure_ascii=False)}\n\n"

    try:
        agent, thread, ctx = _build_context(db, user_id, body)
    except Exception as e:
        yield emit("error", {"msg": str(e)})
        yield "data: [DONE]\n\n"
        return

    yield emit("meta", {"thread_id": thread.thread_id, "agent_name": agent.name})

    runner = get_runner(agent.architecture)
    stream_fn = getattr(runner, "run_stream", None)
    final_reply = ""
    final_thinking = ""
    final_tools: list = []
    final_steps: list = []
    final_citations: list = []

    if stream_fn is None:
        # 不支持流式,降级到同步
        try:
            result: RunResult = runner.run(ctx)
        except Exception as e:
            logger.exception(f"agent run failed: {e}")
            yield emit("error", {"msg": str(e)})
            yield "data: [DONE]\n\n"
            return
        final_reply = result.reply
        final_tools = result.tool_calls
        final_steps = result.steps
        final_citations = result.citations or []
        yield emit("delta", {"delta": result.reply})
    else:
        try:
            for ev in stream_fn(ctx):
                t = ev["type"]; d = ev["data"]
                if t == "done":
                    final_reply = d.get("reply", "")
                    final_thinking = d.get("thinking", "")
                    final_tools = d.get("tool_calls", [])
                    final_steps = d.get("steps", [])
                    final_citations = d.get("citations", []) or []
                yield emit(t, d)
        except Exception as e:
            logger.exception(f"stream failed: {e}")
            yield emit("error", {"msg": str(e)})
            yield "data: [DONE]\n\n"
            return

    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="user", content=body.message))
    db.add(AgentChatMessage(thread_id=thread.thread_id, agent_name=agent.name,
                            user_id=user_id, role="assistant", content=final_reply))
    if thread.title == "新对话":
        thread.title = body.message[:30]
    thread.last_message = final_reply[:200]
    db.commit()

    yield emit("meta", {"title": thread.title})
    yield "data: [DONE]\n\n"


# ============ Thread CRUD ============
def list_threads(db: Session, user_id: int, agent_name: str | None = None) -> list[ChatThread]:
    stmt = select(ChatThread).where(ChatThread.user_id == user_id, ChatThread.enabled.is_(True))
    if agent_name:
        stmt = stmt.where(ChatThread.agent_name == agent_name)
    return list(db.scalars(stmt.order_by(desc(ChatThread.updated_at))).all())


def get_thread(db: Session, thread_id: str, user_id: int) -> ChatThread:
    obj = db.scalar(select(ChatThread).where(ChatThread.thread_id == thread_id, ChatThread.user_id == user_id))
    if not obj:
        raise ErrNotFound("会话不存在")
    return obj


def rename_thread(db: Session, thread_id: str, user_id: int, title: str) -> ChatThread:
    obj = get_thread(db, thread_id, user_id)
    obj.title = title
    db.commit()
    db.refresh(obj)
    return obj


def delete_thread(db: Session, thread_id: str, user_id: int) -> None:
    obj = get_thread(db, thread_id, user_id)
    obj.enabled = False
    db.commit()


def list_messages(db: Session, thread_id: str, user_id: int, limit: int = 100) -> list[AgentChatMessage]:
    get_thread(db, thread_id, user_id)
    return list(db.scalars(
        select(AgentChatMessage)
        .where(AgentChatMessage.thread_id == thread_id)
        .order_by(AgentChatMessage.id.asc()).limit(limit)
    ).all())
