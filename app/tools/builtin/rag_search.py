"""rag_search 工具: 在 Agent 绑定的知识库中检索
参数: {"query": str, "kb_ids"?: list[int], "top_k"?: int}
- kb_ids 不传则用 agent.rag_kb_ids (绑定时默认)
- 返回拼接的 chunk 文本, 带 [doc:xxx p.N] 引用
"""
from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from app.tools import BaseTool
from app.schemas.rag import QueryIn


class RagSearchTool(BaseTool):
    name = "rag_search"
    display_name = "知识库检索"
    description = (
        "在绑定的知识库中检索资料。当你需要查产品手册、企业文档、政策、FAQ 时使用。"
        "不要用它回答常识问题或与知识库无关的问题。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要检索的问题或关键词,用自然语言描述"},
            "top_k": {"type": "integer", "description": "返回的最相关片段数量", "default": 5},
        },
        "required": ["query"],
    }

    def run(self, ctx: Any, **kwargs) -> str:
        query = kwargs.get("query", "").strip()
        top_k = int(kwargs.get("top_k", 5))
        if not query:
            return "[rag_search] 错误: query 不能为空"

        # 确定知识库范围: 显式 kb_ids 优先, 否则用 agent 绑定的
        kb_ids = kwargs.get("kb_ids") or getattr(ctx.agent, "rag_kb_ids", []) or []
        if isinstance(kb_ids, int):
            kb_ids = [kb_ids]
        if not kb_ids:
            return "[rag_search] 未绑定知识库,请在 Agent 设置中绑定知识库后再检索"

        db: Session = ctx.db
        from app.services import rag_service
        # 对每个 kb 检索,合并结果
        all_hits = []
        for kb_id in kb_ids:
            try:
                hits = rag_service.query_documents(
                    db,
                    QueryIn(kb_id=kb_id, query=query, top_k=top_k, rerank=True, return_content=True),
                )
                for h in hits:
                    h["kb_id"] = kb_id
                    all_hits.append(h)
            except Exception as e:
                all_hits.append({"content": f"[检索知识库{kb_id}失败: {e}]", "score": 0, "document_name": "",
                                 "chunk_index": 0, "kb_id": kb_id})
        if not all_hits:
            return "[rag_search] 未找到相关资料"

        # 按 score 降序, 去重 content, 截断 top_k
        all_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        seen, unique = set(), []
        for h in all_hits:
            c = h["content"]
            if c in seen:
                continue
            seen.add(c)
            unique.append(h)
            if len(unique) >= top_k:
                break

        lines = []
        # 获取 ctx 上已有的 citations 数量,继续累加编号
        existing = getattr(ctx, "citations", None)
        if existing is None:
            existing = []
            try:
                ctx.citations = existing
            except Exception:
                pass
        base_idx = len(existing) + 1
        for i, h in enumerate(unique, base_idx):
            name = h.get("document_name", "")
            # 累积结构化引用(前端角标用)
            try:
                existing.append({
                    "idx": i,
                    "chunk_id": h.get("chunk_id"),
                    "document_id": h.get("document_id"),
                    "document_name": name,
                    "kb_id": h.get("kb_id"),
                    "chunk_index": h.get("chunk_index"),
                    "content": h.get("content", ""),
                    "score": h.get("score", 0),
                })
            except Exception:
                pass
            lines.append(f"[{i}] {h['content']}\n   来源: {name}")
        return "\n\n".join(lines)
