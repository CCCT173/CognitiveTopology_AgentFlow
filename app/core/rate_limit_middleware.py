"""
全局 API 限流中间件: 基于 IP 的滑动窗口限流
- 白名单: /health, /docs, /openapi.json, /static
- 默认 100 req/min/IP
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security_utils import api_limiter

WHITELIST_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/favicon.ico",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in WHITELIST_PREFIXES):
            # 取客户端 IP（考虑 X-Forwarded-For）
            client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
            if "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()
            try:
                api_limiter.check_and_hit(client_ip)
            except Exception as e:
                # AppException 已带 http_status=429
                status = getattr(e, "http_status", 429)
                msg = getattr(e, "message", str(e))
                code = getattr(e, "code", "RATE_LIMIT")
                return JSONResponse(
                    status_code=status,
                    content={"code": code, "message": msg},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
