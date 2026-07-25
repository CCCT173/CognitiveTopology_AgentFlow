"""工作流 ORM 模型 (Workflow + WorkflowRun)
工作流 = 节点+边的有向图,可以编排多个 Agent / 工具 / 知识库调用
definition 存 JSON(前端可视化拖拽生成),执行逻辑后续实现
WorkflowRun 记录每次工作流执行的历史: 输入/输出/日志/耗时/状态
"""
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, JSON, BigInteger, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now, utc_now_naive


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="工作流名称")
    display_name: Mapped[str] = mapped_column(String(128), default="", comment="显示名称")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="", comment="分类标签")
    user_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True, comment="创建者 user_id")
    definition: Mapped[dict] = mapped_column(JSON, default=dict, comment="工作流图定义(JSON)")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="乐观锁版本号")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive,
                                                  onupdate=utc_now_naive, nullable=False)


class WorkflowRun(Base):
    """工作流执行历史记录"""
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="运行ID (UUID)")
    workflow_id: Mapped[int] = mapped_column(BigInteger, index=True)
    workflow_name: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    status: Mapped[str] = mapped_column(String(16), default="running", comment="success/failed/running")
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="输入参数")
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="输出结果")
    logs: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="执行日志 (string[])")
    node_outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="各节点输出")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False, index=True)

    __table_args__ = (
        # 高频查询: 按 workflow_id 取最近运行 (WF详情页历史面板)
        Index("ix_wf_runs_wf_created", "workflow_id", "created_at"),
        # 高频查询: 按状态统计成功率 (Dashboard接口)
        Index("ix_wf_runs_status", "status"),
    )
