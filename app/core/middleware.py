"""
替换 BaseHTTPMiddleware，避免对 StreamingResponse（特别是 SSE）的缓冲问题。

Starlette/FastAPI 的 BaseHTTPMiddleware 在 dispatch() 结束后会把 response.body_iterator
整个读一遍，破坏 SSE/Chunked 流式响应。这里用 Pure ASGI middleware 直接透传，
同时保留 request_id 注入和访问日志功能。
"""
import time
import uuid
import logging
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

logger = logging.getLogger("app.http")

# SSE content types that should never be buffered/consumed
_SSE_CTYPES = ("text/event-stream",)


def _is_sse(message) -> bool:
    """从 ASGI start message 的 headers 里检测 SSE content-type"""
    headers = dict(message.get("headers", []))
    ct = headers.get(b"content-type", b"").decode("latin-1", errors="replace").lower()
    return any(t in ct for t in _SSE_CTYPES)


class RequestContextMiddleware:
    """Pure ASGI middleware: 注入 X-Request-ID + 访问日志 + APM, 不缓冲响应体"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = None
        for k, v in scope.get("headers", []):
            if k.lower() == b"x-request-id":
                rid = v.decode("latin-1", errors="replace")
                break
        if not rid:
            rid = uuid.uuid4().hex[:16]

        # 把 request_id 放到 scope state 里供后续使用
        scope.setdefault("state", {})
        # scope["state"] 在 ASGI 是一个 _ScopeState; 用 dict 兼容
        try:
            scope["state"]["request_id"] = rid
        except Exception:
            pass

        start = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "")
        sse_stream = {"flag": False}  # 用 dict 让内部 closure 可写
        status_code = {"code": 0}
        first_byte_time = [None]

        async def wrapped_send(message):
            mtype = message.get("type")
            if mtype == "http.response.start":
                status_code["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                # 注入 X-Request-ID
                headers.append((b"x-request-id", rid.encode("latin-1")))
                # 检测 SSE
                if _is_sse(message):
                    sse_stream["flag"] = True
                    # 对于 SSE, 确保 X-Accel-Buffering: no 禁用代理缓冲
                    has_xa = any(k.lower() == b"x-accel-buffering" for k, _ in headers)
                    if not has_xa:
                        headers.append((b"x-accel-buffering", b"no"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            dur = (time.time() - start) * 1000
            if not path.startswith(("/files", "/health")):
                logger.info(f"[{rid}] {method} {path} {status_code['code']} {dur:.0f}ms")
            try:
                from app.core.apm import apm
                apm.record(method, path, status_code["code"], dur)
            except Exception:
                pass
