"""RAG 知识库 / 文档 / Chunk 请求响应模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============ 知识库 ============
class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    category: str = ""
    description: str = ""
    embedding_model: str = ""
    loader: str = "text"                # text/pdf/docx/markdown/image/...
    splitter_type: str = "sentence"     # token/sentence/regex/semantic
    splitter_regex: str = ""            # splitter_type=regex 时的分隔正则
    chunk_size: int = 500
    chunk_overlap: int = 50
    icon_url: str = ""


class KBUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    loader: Optional[str] = None
    splitter_type: Optional[str] = None
    splitter_regex: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    enabled: Optional[bool] = None
    icon_url: Optional[str] = None


class KBOut(BaseModel):
    id: int
    name: str
    category: str
    description: str
    embedding_model: str
    loader: str
    splitter_type: str
    splitter_regex: str
    chunk_size: int
    chunk_overlap: int
    icon_url: str
    created_by: Optional[int] = None
    document_count: int = 0
    total_chunks: int = 0
    enabled: bool
    vector_collection: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ============ 文档 ============
class DocumentUpdate(BaseModel):
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    metadata_: Optional[dict] = None


class DocumentOut(BaseModel):
    id: int
    name: str                    # 原始文件名(不可改)
    display_name: str            # 显示名(可改)
    kb_id: int
    file_size: int
    content_type: str
    chunk_count: int
    status: str
    enabled: bool
    metadata_: dict = {}
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ============ Chunk ============
class ChunkCreate(BaseModel):
    """手工新增一个 chunk"""
    content: str = Field(..., min_length=1)
    chunk_index: Optional[int] = None   # 不传则追加末尾
    metadata_: dict = {}


class ChunkUpdate(BaseModel):
    """修改 chunk 内容/序号"""
    content: Optional[str] = None
    chunk_index: Optional[int] = None
    metadata_: Optional[dict] = None


class ChunkOut(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    token_count: int
    metadata_: dict
    created_at: datetime
    model_config = {"from_attributes": True}


# ============ 检索 ============
class QueryIn(BaseModel):
    kb_id: int
    query: str
    top_k: int = 5
    hybrid: bool = True
    rerank: bool = True
    return_content: bool = True


class QueryResult(BaseModel):
    chunk_id: int
    document_id: int
    document_name: str
    content: str
    score: float
