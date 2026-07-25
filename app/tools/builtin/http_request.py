"""http_request 工具: 发送 HTTP 请求获取网页/API 内容
参数: {"url": str, "method"?: "GET"|"POST", "headers"?: dict, "body"?: str, "timeout"?: int}
- 默认 GET, timeout 默认 10 秒
- 响应截取前 8000 字符返回
- 仅允许 http/https 协议
"""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse
from app.tools import BaseTool


class HttpRequestTool(BaseTool):
    name = "http_request"
    display_name = "HTTP 请求"
    description = (
        "发送 HTTP 请求获取指定 URL 的内容,支持 GET/POST。适用于抓取公开网页、"
        "调用开放 API、下载 JSON 数据。请求前需确认 URL 是公开可访问的。响应自动截断到 8KB。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "目标 URL,必须以 http:// 或 https:// 开头"},
            "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET", "description": "请求方法"},
            "headers": {"type": "object", "description": "请求头,如 {\"User-Agent\":\"Mozilla/5.0\"}", "additionalProperties": {"type": "string"}},
            "body": {"type": "string", "description": "POST 请求体内容"},
            "timeout": {"type": "integer", "description": "超时秒数(1-30)", "default": 10, "minimum": 1, "maximum": 30},
        },
        "required": ["url"],
    }

    MAX_BYTES = 8000

    def run(self, ctx: Any, **kwargs) -> str:
        url = kwargs.get("url", "").strip()
        if not url:
            return "[http_request] 错误: url 不能为空"
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "[http_request] 错误: URL 非法,仅支持 http/https"
        method = kwargs.get("method", "GET").upper()
        headers = kwargs.get("headers") or {}
        body = kwargs.get("body")
        timeout = max(1, min(30, int(kwargs.get("timeout", 10))))

        # 默认 UA 避免被墙
        headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 AgentRAG/1.0")

        try:
            import requests
            resp = requests.request(method, url, headers=headers, data=body, timeout=timeout, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "")
            text = resp.text
            truncated = False
            if len(text) > self.MAX_BYTES:
                text = text[:self.MAX_BYTES]
                truncated = True
            out = f"[http_request] HTTP {resp.status_code} {resp.reason}\nContent-Type: {content_type}\nURL(final): {resp.url}\n\n{text}"
            if truncated:
                out += f"\n\n[... 内容过长,已截断到 {self.MAX_BYTES} 字符,URL 总长度 {len(resp.text)} 字符]"
            return out
        except Exception as e:
            return f"[http_request] 请求失败: {type(e).__name__}: {e}"
