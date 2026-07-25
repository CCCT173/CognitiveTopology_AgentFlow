from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="技能名称")
    description: Optional[str] = Field(None, description="技能描述")
    version: str = Field("1.0.0", description="版本号")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    is_active: bool = Field(True, description="是否启用")

class SkillCreate(SkillBase):
    content: str = Field(..., min_length=10, description="SKILL.md内容")
    entry_point: Optional[str] = Field(None, max_length=255, description="入口点")
    code: Optional[str] = Field(None, description="代码内容")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置schema")

class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    entry_point: Optional[str] = None
    code: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class SkillResponse(SkillBase):
    id: int
    is_builtin: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SkillDetail(SkillResponse):
    content: str
    entry_point: Optional[str] = None
    code: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

class SkillTestRequest(BaseModel):
    input_params: Dict[str, Any] = Field(default_factory=dict, description="测试输入参数")
    context: Optional[str] = Field(None, description="测试上下文")

class SkillTestResponse(BaseModel):
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time: float = Field(description="执行时间(秒)")
    logs: List[str] = Field(default_factory=list, description="执行日志")

class SkillImportRequest(BaseModel):
    content: str = Field(..., description="要导入的Skill内容(zip/base64/SKILL.md文本)")
    format: str = Field("markdown", description="导入格式：markdown/zip/url")
