"""
Agent 对话接口 + 会话历史
  POST  /api/v1/chat                    发送消息(传 thread_id 续聊,不传则新建)
  POST  /api/v1/chat/stream             流式发送消息(SSE)
  GET   /api/v1/chat/threads            会话列表(可按 agent_name 过滤)
  GET   /api/v1/chat/threads/{tid}      会话详情(含消息列表)
  PATCH /api/v1/chat/threads/{tid}      重命名会话
  DELETE /api/v1/chat/threads/{tid}     删除会话
"""
import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ok
from app.schemas.agent import ChatIn, ChatOut
from app.schemas.chat import ThreadOut, ThreadRename, MessageOut
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["Agent对话"])


@router.post("", summary="发送消息")
async def send_message(
    body: ChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await chat_service.chat_async(db, user.user_id, body)
    return ok(ChatOut(**result).model_dump())


@router.post("/stream", summary="流式发送消息(SSE)")
def send_message_stream(
    body: ChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """返回 SSE 流, event:
      data: {"type":"meta","thread_id":...,"agent_name":...}
      data: {"type":"thinking","delta":"..."}
      data: {"type":"delta","delta":"..."}
      data: {"type":"tool","tool":"...","args":...,"result":"..."}
      data: {"type":"step","iter":1,"tool_calls":[...]}
      data: {"type":"done",...}
      data: {"type":"error","msg":"..."}
      data: [DONE]
    """
    gen = chat_service.chat_stream(db, user.user_id, body)
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@router.get("/threads", summary="我的会话列表")
def list_threads(
    agent_name: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    threads = chat_service.list_threads(db, user.user_id, agent_name)
    return ok([ThreadOut.model_validate(t).model_dump() for t in threads])


@router.get("/threads/{thread_id}", summary="会话详情+消息")
def get_thread(
    thread_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    thread = chat_service.get_thread(db, thread_id, user.user_id)
    msgs = chat_service.list_messages(db, thread_id, user.user_id, limit)
    data = ThreadOut.model_validate(thread).model_dump()
    data["messages"] = [MessageOut.model_validate(m).model_dump() for m in msgs]
    return ok(data)


@router.patch("/threads/{thread_id}", summary="重命名会话")
def rename_thread(
    thread_id: str,
    body: ThreadRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = chat_service.rename_thread(db, thread_id, user.user_id, body.title)
    return ok(ThreadOut.model_validate(t).model_dump())


@router.delete("/threads/{thread_id}", summary="删除会话")
def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat_service.delete_thread(db, thread_id, user.user_id)
    return ok(msg="已删除")


@router.get("/threads/{thread_id}/export", summary="导出会话")
def export_thread(
    thread_id: str,
    fmt: str = Query("json", pattern="^(json|md|markdown)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导出会话为 JSON 或 Markdown 文件"""
    thread = chat_service.get_thread(db, thread_id, user.user_id)
    msgs = chat_service.list_messages(db, thread_id, user.user_id, 1000)
    if fmt == "json":
        payload = {
            "thread_id": thread.thread_id,
            "agent_name": thread.agent_name,
            "title": thread.title,
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_call": m.tool_call,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ],
        }
        from fastapi.responses import Response
        import json as _json
        body = _json.dumps(payload, ensure_ascii=False, indent=2)
        filename = f"thread_{thread.thread_id}.json"
        return Response(
            content=body, media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    # Markdown
    lines = [
        f"# {thread.title or '对话记录'}",
        "",
        f"- Agent: `{thread.agent_name}`",
        f"- 创建时间: {thread.created_at.isoformat() if thread.created_at else ''}",
        f"- 消息数: {len(msgs)}",
        "", "---", "",
    ]
    for m in msgs:
        role_label = {"user": "👤 用户", "assistant": "🤖 Assistant", "system": "⚙️ System"}.get(m.role, m.role)
        lines.append(f"## {role_label}")
        lines.append("")
        lines.append(m.content or "")
        if m.tool_call:
            try:
                lines.append("")
                lines.append("```json")
                lines.append(_safe_json(m.tool_call))
                lines.append("```")
            except Exception:
                pass
        lines.append("")
    body_md = "\n".join(lines)
    filename = f"thread_{thread.thread_id}.md"
    from fastapi.responses import Response
    return Response(
        content=body_md, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_json(v):
    import json as _json
    return _json.dumps(v, ensure_ascii=False, indent=2)
