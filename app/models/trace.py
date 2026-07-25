"""
Trace/Span 模型：每个请求/对话/工具调用产生 trace 链
- trace_id: 一次用户请求
- span_id: 单个操作（LLM 调用、工具执行、沙箱运行）
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now_naive


class Trace(Base):
    """一次完整请求的 trace"""
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="UUID")
    # agent/workflow/chat/mcp
    kind: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0, index=True)
    started_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    finished_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    # kind=agent 时 agent_id；kind=workflow 时 wf_id 等
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True)
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Span(Base):
    """trace 内的单个操作"""
    __tablename__ = "spans"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    span_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), ForeignKey("traces.trace_id"), index=True)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    # llm/tool/sandbox/agent_step
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[object] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    finished_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    __table_args__ = (
        Index("ix_spans_trace_kind", "trace_id", "kind"),
    )
