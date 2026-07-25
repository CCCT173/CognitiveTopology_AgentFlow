from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean, JSON
from app.db.session import Base
from app.core.time import utc_now, utc_now_naive

class Skill(Base):
    """Skill技能模型"""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False, comment="技能名称")
    description = Column(Text, nullable=True, comment="技能描述")
    version = Column(String(20), default="1.0.0", comment="版本号")
    author = Column(String(100), nullable=True, comment="作者")
    category = Column(String(50), nullable=True, index=True, comment="分类：agent/tool/workflow/utility等")
    tags = Column(JSON, default=list, comment="标签列表")

    # Skill核心内容
    content = Column(Text, nullable=False, comment="SKILL.md完整内容")
    entry_point = Column(String(255), nullable=True, comment="入口文件/函数")
    code = Column(Text, nullable=True, comment="关联代码内容")
    config = Column(JSON, default=dict, comment="配置参数schema")

    # 元信息
    created_by = Column(BigInteger, nullable=True, index=True, comment="创建者 user_id")
    is_builtin = Column(Boolean, default=False, comment="是否内置技能")
    is_active = Column(Boolean, default=True, comment="是否启用")
    usage_count = Column(Integer, default=0, comment="使用次数")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # 时间戳
    created_at = Column(DateTime, default=utc_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, comment="更新时间")
    
    def __repr__(self):
        return f"<Skill {self.name} v{self.version}>"
