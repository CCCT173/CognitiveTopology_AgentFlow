"""Agent 请求/响应模型

architecture 取值:
  single    - 单Agent,一次LLM调用(可选工具)
  react     - ReAct 思考-行动-观察 循环
  workflow  - 工作流入口(执行关联的 workflow)
  skill     - 技能子Agent,只能被其他Agent调用

framework 取值 (仅 architecture=workflow 时有意义):
  ""         - 内部实现
  langgraph  - LangGraph runtime
  crewai     - CrewAI Flow/Crew
  autogen    - AutoGen GroupChat

llm_config 字段 (均可自由覆盖,未传则使用模型默认值):
  provider           : giteeai / ark / deepseek (覆盖 settings.LLM_PROVIDER)
  model              : 模型名
  temperature        : 0~2, 默认 1.0
  top_p              : 0~1, 默认 1.0
  max_tokens         : 最大输出 tokens (None=不限制)
  presence_penalty   : -2~2, 默认 0
  frequency_penalty  : -2~2, 默认 0
  stream             : 是否流式输出, 默认 True
  thinking           : 是否开启并展示思考内容, 默认 True
  extra_body         : 透传给 OpenAI 兼容接口的额外 body (如 reasoning_effort 等)
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# LLM 参数默认值(与 app.services.llm.LLM_DEFAULTS 对齐)
DEFAULT_LLM_CONFIG: dict = {
    "temperature": 1.0,
    "top_p": 1.0,
    "max_tokens": None,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "stream": True,
    "thinking": True,
}


def _merge_llm_config(cfg: dict | None) -> dict:
    """用用户传入的 cfg 覆盖 DEFAULT_LLM_CONFIG, 返回新 dict"""
    out = dict(DEFAULT_LLM_CONFIG)
    if cfg:
        for k, v in cfg.items():
            if v is None and k in ("max_tokens",):
                out[k] = None
            else:
                out[k] = v
    return out


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="唯一英文标识")
    display_name: str = ""
    description: str = ""
    framework: str = ""                 # 仅 workflow 架构生效
    architecture: str = "single"        # single/react/workflow/skill
    system_prompt: str = ""
    tools: list[str] = []
    rag_kb_ids: list[int] = []
    llm_config: dict = Field(default_factory=lambda: dict(DEFAULT_LLM_CONFIG))
    workflow_id: Optional[int] = None   # architecture=workflow 时关联
    parent_agent_id: Optional[int] = None  # architecture=skill 时父 agent
    max_iterations: int = 10


class AgentUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    framework: Optional[str] = None
    architecture: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[str]] = None
    rag_kb_ids: Optional[list[int]] = None
    llm_config: Optional[dict] = None
    workflow_id: Optional[int] = None
    parent_agent_id: Optional[int] = None
    max_iterations: Optional[int] = None
    enabled: Optional[bool] = None


class AgentOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    framework: str
    architecture: str
    system_prompt: str
    enabled: bool
    tools: list
    rag_kb_ids: list
    llm_config: dict
    workflow_id: Optional[int] = None
    parent_agent_id: Optional[int] = None
    max_iterations: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToggleEnable(BaseModel):
    enabled: bool


class ChatIn(BaseModel):
    agent_name: str
    message: str
    thread_id: str = ""           # 不传则新建会话
    stream: bool | None = None    # None=使用 agent.llm_config.stream 配置
    variables: dict = {}     # 传给工作流/agent 的额外变量


class ChatOut(BaseModel):
    reply: str
    thinking: str = ""        # 思考内容(若模型返回)
    thread_id: str
    tool_calls: list[dict] = []
    # 多步推理时返回中间步骤(ReAct/工作流节点)
    steps: list[dict] = []
    # RAG 等工具产生的结构化引用来源 [{idx,chunk_id,document_id,document_name,content,score}]
    citations: list[dict] = []


class ChatStreamEvent(BaseModel):
    """SSE 事件:
      type=meta     - 元信息(thread_id/title)
      type=thinking - 思考内容增量
      type=delta    - 正文增量
      type=tool     - 工具调用 {tool,args,result}
      type=step     - ReAct 步骤 {iter,...}
      type=done     - 结束 {reply,thinking,tool_calls,steps}
      type=error    - 错误 {msg}
    """
    type: str
    data: dict = {}
