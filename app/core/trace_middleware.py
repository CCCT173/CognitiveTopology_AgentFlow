"""Trace 中间件 - 为每个 HTTP 请求创建 Trace 和 Span

记录：
- HTTP 请求（path/method/status/duration/client_ip）
- 自动生成 trace_id（16 位 hex）通过 response header X-Trace-Id 返回
- contextvars 传递 trace_id，业务代码可读取以添加子 span
"""
from __future__ import annotations
import contextvars
import json
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.time import utc_now_naive

current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_trace_id", default=None)
current_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_span_id", default=None)


def _short_uuid() -> str:
    return uuid.uuid4().hex[:16]


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 跳过静态/health/OPTIONS
        if path in ("/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"):
            return await call_next(request)
        if path.startswith("/files/") or path.startswith("/static/"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        trace_id = _short_uuid()
        span_id = _short_uuid()
        token_t = current_trace_id.set(trace_id)
        token_s = current_span_id.set(span_id)
        started_at = utc_now_naive()
        start = time.perf_counter()

        # 创建 trace（延迟 import 避免循环依赖）
        db = None
        db_trace = None
        try:
            from app.db.session import SessionLocal
            from app.models.trace import Trace, Span
            db = SessionLocal()
            try:
                db_trace = Trace(
                    trace_id=trace_id,
                    kind="http",
                    started_at=started_at,
                    status="running",
                    input_summary=f"{request.method} {path}",
                )
                db.add(db_trace)
                db.commit()
                db.refresh(db_trace)
            except Exception:
                db.rollback()
                db_trace = None
        except Exception:
            db = None

        response: Response | None = None
        status_code = 500
        error_msg = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            finished_at = utc_now_naive()
            if db is not None:
                try:
                    client_ip = request.client.host if request.client else ""
                    user_agent = request.headers.get("user-agent", "")[:200]
                    user_id = None
                    auth = request.headers.get("authorization", "")
                    if auth.startswith("Bearer "):
                        try:
                            from app.core.security import decode_token
                            user_id = decode_token(auth[7:])
                        except Exception:
                            pass
                    query = str(request.url.query)[:500]
                    from app.models.trace import Span
                    span = Span(
                        trace_id=trace_id,
                        span_id=span_id,
                        kind="http",
                        name=f"{request.method} {path}",
                        started_at=started_at,
                        finished_at=finished_at,
                        status="ok" if status_code < 400 else "error",
                        input_summary=json.dumps({
                            "method": request.method, "path": path, "query": query,
                            "client_ip": client_ip, "user_agent": user_agent, "user_id": user_id,
                        }, ensure_ascii=False)[:2000],
                        output_summary=json.dumps({"status_code": status_code}, ensure_ascii=False),
                        error=error_msg,
                        duration_ms=duration_ms,
                        metadata_json=json.dumps({}),
                    )
                    db.add(span)
                    if db_trace:
                        db_trace.status = "ok" if status_code < 500 else "error"
                        db_trace.duration_ms = duration_ms
                        db_trace.finished_at = finished_at
                        db_trace.user_id = user_id or 0
                        if error_msg:
                            db_trace.error = error_msg
                    db.commit()
                except Exception:
                    try: db.rollback()
                    except Exception: pass
                finally:
                    try: db.close()
                    except Exception: pass
            current_trace_id.reset(token_t)
            current_span_id.reset(token_s)


def add_child_span(*, kind: str, name: str, input_data=None, output_data=None,
                  duration_ms: int = 0, error: str | None = None, tokens_in: int = 0,
                  tokens_out: int = 0) -> str | None:
    """业务代码调用：在当前 trace 下添加子 span。返回 span_id。"""
    trace_id = current_trace_id.get()
    if not trace_id:
        return None
    span_id = _short_uuid()
    try:
        from app.db.session import SessionLocal
        from app.models.trace import Span
        db = SessionLocal()
        try:
            now = utc_now_naive()
            db.add(Span(
                trace_id=trace_id, span_id=span_id,
                parent_span_id=current_span_id.get(),
                kind=kind, name=name,
                started_at=now, finished_at=now,
                status="error" if error else "ok",
                input_summary=json.dumps(input_data or {}, ensure_ascii=False, default=str)[:2000],
                output_summary=json.dumps(output_data or {}, ensure_ascii=False, default=str)[:2000],
                error=error, duration_ms=duration_ms,
                tokens_in=tokens_in, tokens_out=tokens_out,
                metadata_json=json.dumps({}),
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass
    return span_id
