"""
数据库连接配置模型
支持多种数据库类型：MySQL、PostgreSQL、MongoDB、SQLite、SQL Server、Oracle
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, JSON, DateTime, func
from app.db.session import Base


class DbConnection(Base):
    """数据库连接配置"""
    __tablename__ = "db_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True, comment="连接名称（唯一标识）")
    display_name = Column(String(200), nullable=True, comment="显示名称")
    db_type = Column(String(50), nullable=False, comment="数据库类型：mysql/postgresql/mongodb/sqlite/sqlserver/oracle")
    host = Column(String(255), nullable=True, comment="主机地址")
    port = Column(Integer, nullable=True, comment="端口号")
    database = Column(String(200), nullable=True, comment="数据库名称")
    username = Column(String(100), nullable=True, comment="用户名")
    password = Column(String(500), nullable=True, comment="加密后的密码")
    charset = Column(String(50), nullable=True, default="utf8mb4", comment="字符编码")
    timeout = Column(Integer, nullable=True, default=30, comment="连接超时时间（秒）")
    extra_config = Column(JSON, nullable=True, comment="额外配置（JSON格式）")
    enabled = Column(Boolean, default=True, comment="是否启用")
    is_default = Column(Boolean, default=False, comment="是否默认连接")
    description = Column(Text, nullable=True, comment="描述")
    created_by = Column(Integer, nullable=True, comment="创建者用户ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<DbConnection(id={self.id}, name={self.name}, db_type={self.db_type})>"
