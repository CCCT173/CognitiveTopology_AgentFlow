"""Agent ORM 模型

字段设计 (架构划分原则):
  - Agent = "执行者",负责单体智能(LLM/工具调用/推理循环)
  - Workflow = "编排者",负责多步骤/多角色/分支/循环/人工介入
  - 不要在 Agent 里重复造 Workflow 的轮子

architecture (智能体架构) 只有 4 种:
  - single:    单 Agent,一次 LLM 调用,可选 function_calling(0~N 次工具)
               适合: 简单问答、RAG 问答、入门演示
  - react:     ReAct 循环,思考→调工具→观察→再思考...
               适合: 需要反复查工具/联网/查数据的场景
  - workflow:  工作流入口,实际执行交给 workflow_service.run_workflow()
               适合: 企业流程、多分支、人工介入 (在 Workflow 画布中编排)
  - skill:     技能型子 Agent,不能被用户直接对话,只能被其他 Agent 当作工具调用
               适合: 把"专家能力"模块化复用

framework (底层框架) 仅对 architecture=workflow/multi_agent 时有意义:
  - ""        : single/react/skill 不使用,内部实现
  - "langgraph": workflow 走 LangGraph runtime
  - "crewai"  : workflow 走 CrewAI Flow/Crew
  - "autogen"  : workflow 走 AutoGen GroupChat
"""
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, JSON, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.time import utc_now, utc_now_naive


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="唯一英文标识")
    display_name: Mapped[str] = mapped_column(String(128), default="", comment="展示名")
    description: Mapped[str] = mapped_column(Text, default="", comment="简介(给用户看)")
    framework: Mapped[str] = mapped_column(String(32), default="",
                                            comment="底层框架: 空/langgraph/crewai/autogen (仅 workflow 架构生效)")
    architecture: Mapped[str] = mapped_column(String(32), default="single",
                                               comment="架构: single/react/workflow/skill")
    system_prompt: Mapped[str] = mapped_column(Text, default="", comment="系统提示词")
    tools: Mapped[list] = mapped_column(JSON, default=list, comment="绑定的工具名列表 (app.tools.TOOLS 中的 key)")
    rag_kb_ids: Mapped[list] = mapped_column(JSON, default=list, comment="绑定的知识库ID列表 (自动注入 rag_search 工具)")
    llm_config: Mapped[dict] = mapped_column(JSON, default=dict,
                                              comment="LLM覆盖配置: {provider, model, temperature, max_tokens}")
    # 针对 workflow 架构: 关联的 workflow_id (可选,留空则用 name 查找)
    workflow_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联的工作流ID(architecture=workflow)")
    # 针对 skill 架构: 父 router agent id (skill 归属)
    parent_agent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="父Agent id(architecture=skill)")
    # ReAct 等推理循环的安全上限
    max_iterations: Mapped[int] = mapped_column(BigInteger, default=10, comment="推理循环最大步数(防止死循环)")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive,
                                                  onupdate=utc_now_naive, nullable=False)


class AgentChatMessage(Base):
    """Agent 历史消息 (按 thread_id 存对话)"""
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / tool / system
    content: Mapped[str] = mapped_column(Text)
    # function-calling 调用记录: {"tool":"xxx","args":{...},"result":"..."}
    tool_call: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class ChatThread(Base):
    """对话会话"""
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    last_message: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive,
                                                  onupdate=utc_now_naive, nullable=False)
