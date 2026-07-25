"""
AuditLog 中间件: 自动记录 POST/PATCH/PUT/DELETE 写操作到 audit_logs 表
- 仅记录 /api/v1/ 下的写操作, 跳过登录/读取/health/static
- 通过 request.state.user 识别用户 (若认证中间件已注入)
- **Pure ASGI 实现**, 不缓冲 StreamingResponse / SSE
"""
from __future__ import annotations
import json
import time
import threading
import logging
from starlette.requests import Request

logger = logging.getLogger(__name__)

_WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
_SKIP_PREFIX = ("/files", "/health", "/api/v1/auth/login", "/api/v1/auth/register",
                "/api/v1/chat/stream", "/api/v1/meta/chat/stream")  # SSE 流直接跳过 audit 拦截

_ACTION_MAP = [
    ("POST",   "/agents",            "create",  "agent"),
    ("PATCH",  "/agents/",           "update",  "agent"),
    ("DELETE", "/agents/",           "delete",  "agent"),
    ("POST",   "/agents/",           "action",  "agent"),
    ("POST",   "/workflows",         "create",  "workflow"),
    ("PATCH",  "/workflows/",        "update",  "workflow"),
    ("DELETE", "/workflows/",        "delete",  "workflow"),
    ("POST",   "/workflows/",        "action",  "workflow"),
    ("POST",   "/skills",            "create",  "skill"),
    ("PATCH",  "/skills/",           "update",  "skill"),
    ("DELETE", "/skills/",           "delete",  "skill"),
    ("POST",   "/skills/",           "action",  "skill"),
    ("POST",   "/skills/import",     "import",  "skill"),
    ("POST",   "/rag/kb",            "create",  "kb"),
    ("PATCH",  "/rag/kb/",           "update",  "kb"),
    ("DELETE", "/rag/kb/",           "delete",  "kb"),
    ("POST",   "/rag/kb/",           "action",  "kb"),
    ("POST",   "/groups",            "create",  "group"),
    ("DELETE", "/groups/",           "delete",  "group"),
    ("POST",   "/groups/",           "action",  "group"),
    ("POST",   "/admin/users",       "create",  "user"),
    ("DELETE", "/admin/users/",      "delete",  "user"),
    ("POST",   "/admin/users/",      "action",  "user"),
]


def _resolve_action(method: str, path: str) -> tuple[str, str, str]:
    for m, prefix, action, resource in _ACTION_MAP:
        if method == m and prefix in path:
            parts = path.rstrip("/").split("/")
            rid = ""
            for p in reversed(parts):
                if p.isdigit():
                    rid = p
                    break
            return action, resource, rid
    return method.lower(), "api", ""


def _parse_user_from_token(headers: dict) -> tuple[int, str]:
    try:
        auth = headers.get(b"authorization", b"").decode("latin-1", errors="replace")
        if auth.startswith("Bearer "):
            from app.core.security import decode_token
            return decode_token(auth[7:].strip()), ""
    except Exception:
        pass
    return 0, ""


class AuditLogMiddleware:
    """Pure ASGI middleware: 记录写操作审计日志, 不消费响应体"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")

        if method not in _WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        if any(path.startswith(p) for p in _SKIP_PREFIX):
            await self.app(scope, receive, send)
            return
        if not path.startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return

        # 读请求体 (允许 body 重放)
        body_chunks = []
        while True:
            msg = await receive()
            if msg["type"] == "http.request":
                body_chunks.append(msg.get("body", b""))
                if not msg.get("more_body", False):
                    break
        body_bytes = b"".join(body_chunks)

        async def replay():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        # 解析用户
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        user_id, _ = _parse_user_from_token(headers)

        action, resource, rid = _resolve_action(method, path)
        # 客户端 IP
        client = scope.get("client")
        ip = client[0] if client else ""
        ua = headers.get(b"user-agent", b"").decode("utf-8", errors="replace")[:256]

        # 解析 body (脱敏)
        detail: dict = {}
        try:
            if body_bytes:
                text = body_bytes.decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        for k in ("password", "password_hash", "token", "api_key", "secret"):
                            if k in parsed:
                                parsed[k] = "***"
                        detail = parsed
                except Exception:
                    detail = {"raw": text[:500]}
        except Exception:
            pass

        start = time.time()
        status_code = {"code": 0}

        async def wrapped_send(message):
            if message.get("type") == "http.response.start":
                status_code["code"] = message.get("status", 0)
                # 注入 x-audit header
                headers = list(message.get("headers", []))
                headers.append((b"x-audit", f"{action}:{resource}:0ms".encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, replay, wrapped_send)
        finally:
            dur = int((time.time() - start) * 1000)
            status = "success" if status_code["code"] < 400 else "failed"
            # 异步写审计日志
            try:
                def _write():
                    try:
                        from app.db.session import SessionLocal
                        from app.models.audit import AuditLog
                        db = SessionLocal()
                        try:
                            db.add(AuditLog(
                                user_id=user_id, username="", action=action,
                                resource=resource, resource_id=rid, detail=detail,
                                ip=ip, user_agent=ua, status=status,
                            ))
                            db.commit()
                        except Exception:
                            db.rollback()
                        finally:
                            db.close()
                    except Exception as e:
                        logger.debug(f"audit write failed: {e}")
                threading.Thread(target=_write, daemon=True).start()
            except Exception:
                pass
