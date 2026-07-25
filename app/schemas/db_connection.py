"""
数据库连接配置的 Pydantic 数据模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any


class DbConnectionCreate(BaseModel):
    """创建数据库连接配置"""
    name: str = Field(..., description="连接名称（唯一标识）")
    display_name: Optional[str] = Field(None, description="显示名称")
    db_type: str = Field(..., description="数据库类型：mysql/postgresql/mongodb/sqlite/sqlserver/oracle")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口号")
    database: Optional[str] = Field(None, description="数据库名称")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码（明文，后端加密存储）")
    charset: Optional[str] = Field("utf8mb4", description="字符编码")
    timeout: Optional[int] = Field(30, description="连接超时时间（秒）")
    extra_config: Optional[dict[str, Any]] = Field(None, description="额外配置（JSON格式）")
    enabled: Optional[bool] = Field(True, description="是否启用")
    is_default: Optional[bool] = Field(False, description="是否默认连接")
    description: Optional[str] = Field(None, description="描述")

    @field_validator('db_type')
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        valid_types = {"mysql", "postgresql", "mongodb", "sqlite", "sqlserver", "oracle"}
        if v.lower() not in valid_types:
            raise ValueError(f"数据库类型必须是: {', '.join(sorted(valid_types))}")
        return v.lower()

    @field_validator('charset')
    @classmethod
    def validate_charset(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in {"utf8", "utf8mb4", "gbk", "gb2312", "latin1", "ascii"}:
            raise ValueError("字符编码必须是: utf8, utf8mb4, gbk, gb2312, latin1, ascii")
        return v


class DbConnectionUpdate(BaseModel):
    """更新数据库连接配置"""
    display_name: Optional[str] = Field(None, description="显示名称")
    db_type: Optional[str] = Field(None, description="数据库类型")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口号")
    database: Optional[str] = Field(None, description="数据库名称")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码（留空则不修改）")
    charset: Optional[str] = Field(None, description="字符编码")
    timeout: Optional[int] = Field(None, description="连接超时时间（秒）")
    extra_config: Optional[dict[str, Any]] = Field(None, description="额外配置（JSON格式）")
    enabled: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, description="是否默认连接")
    description: Optional[str] = Field(None, description="描述")

    @field_validator('db_type')
    @classmethod
    def validate_db_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid_types = {"mysql", "postgresql", "mongodb", "sqlite", "sqlserver", "oracle"}
        if v.lower() not in valid_types:
            raise ValueError(f"数据库类型必须是: {', '.join(sorted(valid_types))}")
        return v.lower()


class DbConnectionOut(BaseModel):
    """数据库连接配置响应（密码脱敏）"""
    id: int
    name: str
    display_name: Optional[str]
    db_type: str
    host: Optional[str]
    port: Optional[int]
    database: Optional[str]
    username: Optional[str]
    password: Optional[str] = Field(None, description="密码（脱敏显示）")
    charset: Optional[str]
    timeout: Optional[int]
    extra_config: Optional[dict[str, Any]]
    enabled: bool
    is_default: bool
    description: Optional[str]
    created_by: Optional[int]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DbConnectionTestIn(BaseModel):
    """测试数据库连接参数"""
    db_type: str = Field(..., description="数据库类型")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口号")
    database: Optional[str] = Field(None, description="数据库名称")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    charset: Optional[str] = Field("utf8mb4", description="字符编码")
    timeout: Optional[int] = Field(10, description="连接超时时间（秒）")
    extra_config: Optional[dict[str, Any]] = Field(None, description="额外配置")


class DbConnectionTestOut(BaseModel):
    """测试数据库连接结果"""
    success: bool
    message: str
    version: Optional[str] = Field(None, description="数据库版本")
    error: Optional[str] = Field(None, description="错误信息")


class DbConnectionImportIn(BaseModel):
    """导入数据库连接配置"""
    connections: list[DbConnectionCreate] = Field(..., description="连接配置列表")


class DbConnectionExportOut(BaseModel):
    """导出数据库连接配置"""
    connections: list[DbConnectionOut] = Field(..., description="连接配置列表")
    export_time: str = Field(..., description="导出时间")
