"""工作流 请求/响应模型"""
import json
from datetime import datetime
from typing import Optional, Any, Union
from pydantic import BaseModel, Field, field_validator


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    display_name: str = ""
    description: str = ""
    category: str = ""
    definition: dict = {}      # 节点/边图定义,前端拖拽生成


class WorkflowUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    definition: Optional[dict] = None
    enabled: Optional[bool] = None
    expected_version: Optional[int] = Field(None, description="乐观锁：更新时期望的版本号")


class WorkflowOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    category: str
    definition: Union[dict, str]  # pymysql 可能返回 str 而非 dict
    enabled: bool
    version: int = 1
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("definition", mode="before")
    @classmethod
    def _parse_definition(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {"nodes": [], "edges": []}
        return v

    model_config = {"from_attributes": True}


class WorkflowRunIn(BaseModel):
    """执行工作流的入参(后续实现)"""
    input: dict = {}           # 输入变量
    sync: bool = True          # 是否同步等待结果
    variables: dict = {}       # 额外变量


class WorkflowRunOut(BaseModel):
    run_id: str
    status: str                # pending/running/success/failed
    output: Any = None
    error: str | None = None
    logs: list[str] = []
    elapsed_ms: int = 0
    node_outputs: dict[str, Any] = {}
