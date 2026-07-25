"""web_search 工具: 联网搜索公开网页 (DuckDuckGo 后端 via ddgs, 无需 API key)
参数: {"query": str, "max_results"?: int, "region"?: str, "time_filter"?: str}
- 默认返回 5 条结果: 标题 + URL + 摘要
- 可选 region: cn-zh(默认中国中文), us-en, wt-wt(全球)
- 可选 time_filter: d/w/m/y (天/周/月/年)
"""
from __future__ import annotations
from typing import Any
from app.tools import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    display_name = "联网搜索"
    description = (
        "搜索公开互联网获取实时信息、新闻、文档、博客等。当你需要回答最新事件、"
        "当前网页内容、最新产品价格/版本号、事实核查等问题时使用。不要用它查公司内部知识(那用 rag_search)。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词,尽量简短明确,不要太长的自然语言"},
            "max_results": {"type": "integer", "description": "返回结果条数(1-10)", "default": 5, "minimum": 1, "maximum": 10},
            "region": {"type": "string", "description": "地区/语言: cn-zh / us-en / wt-wt(全球)", "default": "cn-zh", "enum": ["cn-zh", "us-en", "wt-wt"]},
            "time_filter": {"type": "string", "description": "时间范围: d=最近一天,w=最近一周,m=最近一月,y=最近一年,留空不限", "enum": ["", "d", "w", "m", "y"]},
        },
        "required": ["query"],
    }

    def run(self, ctx: Any, **kwargs) -> str:
        query = kwargs.get("query", "").strip()
        if not query:
            return "[web_search] 错误: query 不能为空"
        max_results = max(1, min(10, int(kwargs.get("max_results", 5))))
        region = kwargs.get("region", "cn-zh") or "cn-zh"
        time_filter = kwargs.get("time_filter", "") or None

        try:
            from ddgs import DDGS
        except ImportError:
            return "[web_search] 错误: ddgs 未安装,请 pip install ddgs"

        try:
            with DDGS(timeout=20) as ddgs:
                kw: dict[str, Any] = dict(
                    region=region,
                    safesearch="moderate",
                    max_results=max_results,
                )
                if time_filter:
                    kw["timelimit"] = time_filter
                results = list(ddgs.text(query, **kw))
        except Exception as e:
            return f"[web_search] 搜索失败: {type(e).__name__}: {e}"

        if not results:
            return "[web_search] 未找到相关结果,可尝试换关键词或放宽时间范围"

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            href = r.get("href", "").strip()
            body = (r.get("body") or r.get("snippet") or "").strip()
            lines.append(f"[{i}] {title}\n    URL: {href}\n    摘要: {body}")
        return "\n\n".join(lines)
