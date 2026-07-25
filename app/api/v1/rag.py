"""
RAG 知识库/文档/Chunk 接口 (带所有权校验)
"""
import os
import uuid
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, ensure_owner_or_admin, is_admin
from app.schemas.common import ok
from app.schemas.rag import (
    KBCreate, KBUpdate, KBOut,
    DocumentOut, DocumentUpdate,
    ChunkOut, ChunkCreate, ChunkUpdate,
    QueryIn,
)
from app.services import rag_service
from app.services.loaders import get_loader, detect_by_filename
from app.core.exceptions import ErrBadRequest, AppException, ErrorCode, ErrForbidden
from app.models.rag import Document, KnowledgeBase, Chunk
from app.models.user import User
from app.core.security import get_current_user_required_enabled
from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/rag", tags=["RAG知识库"])

ALLOWED_ICON_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}
ALLOWED_DOC_MAGIC = {
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF8": "image/gif",
    b"RIFF": "image/webp",
    b"PK\x03\x04": "application/zip (docx)",
    b"%PDF": "application/pdf",
}


# ============ 权限辅助 ============
def _check_kb(db: Session, kb_id: int, user: User) -> KnowledgeBase:
    kb = rag_service.get_kb(db, kb_id)
    ensure_owner_or_admin(user, kb.created_by, "知识库")
    return kb


def _check_doc(db: Session, doc_id: int, user: User) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        from app.core.exceptions import ErrNotFound
        raise ErrNotFound("文档不存在")
    _check_kb(db, doc.kb_id, user)
    return doc


def _check_chunk(db: Session, chunk_id: int, user: User) -> Chunk:
    chunk = db.get(Chunk, chunk_id)
    if not chunk:
        from app.core.exceptions import ErrNotFound
        raise ErrNotFound("切块不存在")
    _check_doc(db, chunk.document_id, user)
    return chunk


# ============ KB ============
def _kb_out(k) -> dict:
    d = KBOut.model_validate(k).model_dump()
    d["document_count"] = getattr(k, "_doc_count", 0)
    d["total_chunks"] = getattr(k, "_total_chunks", 0)
    return d


@router.get("/kbs", summary="知识库列表")
def list_kbs(db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    owner_id = None if is_admin(user) else user.user_id
    return ok([_kb_out(k) for k in rag_service.list_kbs(db, owner_id=owner_id)])


@router.post("/kbs", summary="创建知识库")
def create_kb(
    body: KBCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    obj = rag_service.create_kb(db, body, user_id=user.user_id)
    return ok(_kb_out(obj))


@router.get("/kbs/{kb_id}", summary="知识库详情")
def get_kb(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_kb(db, kb_id, user)
    return ok(_kb_out(rag_service.get_kb(db, kb_id)))


@router.patch("/kbs/{kb_id}", summary="更新知识库配置")
def update_kb(kb_id: int, body: KBUpdate, db: Session = Depends(get_db),
              user: User = Depends(get_current_user_required_enabled)):
    _check_kb(db, kb_id, user)
    obj = rag_service.update_kb(db, kb_id, body)
    return ok(_kb_out(rag_service.get_kb(db, kb_id)))


@router.delete("/kbs/{kb_id}", summary="删除知识库")
def delete_kb(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_kb(db, kb_id, user)
    rag_service.delete_kb(db, kb_id)
    return ok(msg="已删除")


@router.post("/kbs/{kb_id}/icon", summary="上传知识库图标")
async def upload_kb_icon(kb_id: int, file: UploadFile = File(...),
                         db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_kb(db, kb_id, user)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_ICON_EXT:
        raise ErrBadRequest(f"仅支持图标: {ALLOWED_ICON_EXT}")
    icon_dir = str(settings.upload_dir_abs / "icons")
    os.makedirs(icon_dir, exist_ok=True)
    fname = f"kb_{kb_id}_{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(icon_dir, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    icon_url = f"/files/icons/{fname}"
    rag_service.set_kb_icon(db, kb_id, icon_url)
    return ok({"icon_url": icon_url})


# ============ 文档 ============
@router.get("/kbs/{kb_id}/documents", summary="文档列表")
def list_docs(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_kb(db, kb_id, user)
    return ok([DocumentOut.model_validate(d).model_dump() for d in rag_service.list_documents(db, kb_id)])


@router.patch("/documents/{doc_id}", summary="修改文档(改显示名/启用)")
def update_doc(doc_id: int, body: DocumentUpdate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user_required_enabled)):
    _check_doc(db, doc_id, user)
    obj = rag_service.update_document(db, doc_id, body)
    return ok(DocumentOut.model_validate(obj).model_dump())


@router.delete("/documents/{doc_id}", summary="删除文档+向量")
def delete_doc(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_doc(db, doc_id, user)
    rag_service.delete_document(db, doc_id)
    return ok(msg="已删除")


# ============ Chunk ============
@router.get("/documents/{doc_id}/chunks", summary="文档 chunk 列表")
def list_chunks(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_doc(db, doc_id, user)
    return ok([ChunkOut.model_validate(c).model_dump() for c in rag_service.list_chunks(db, doc_id)])


@router.post("/documents/{doc_id}/chunks", summary="新增 chunk (自动向量化)")
def create_chunk(doc_id: int, body: ChunkCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user_required_enabled)):
    _check_doc(db, doc_id, user)
    c = rag_service.create_chunk(db, doc_id, body)
    rag_service.query_cache_clear()
    return ok(ChunkOut.model_validate(c).model_dump(), msg="已新增")


@router.patch("/chunks/{chunk_id}", summary="修改 chunk (内容变更会重新向量化)")
def update_chunk(chunk_id: int, body: ChunkUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user_required_enabled)):
    _check_chunk(db, chunk_id, user)
    c = rag_service.update_chunk(db, chunk_id, body)
    rag_service.query_cache_clear()
    return ok(ChunkOut.model_validate(c).model_dump())


@router.delete("/chunks/{chunk_id}", summary="删除 chunk + 向量")
def delete_chunk(chunk_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    _check_chunk(db, chunk_id, user)
    rag_service.delete_chunk(db, chunk_id)
    rag_service.query_cache_clear()
    return ok(msg="已删除")


# ============ 上传(异步) + 检索 ============
def _validate_magic(raw: bytes, filename: str):
    head = raw[:8]
    for magic in ALLOWED_DOC_MAGIC:
        if head.startswith(magic):
            return
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        raise AppException(ErrorCode.UPLOAD_FAILED, f"文件内容不是文本也不是已知格式: {filename}")


def _index_task(doc_id: int, kb_id: int, fpath: str, raw: bytes,
                loader: str, splitter_type: str, splitter_regex: str,
                chunk_size: int, chunk_overlap: int):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if not doc:
            return
        doc.status = "indexing"
        db.commit()
        try:
            loader_obj = get_loader(loader)
            segments = loader_obj.load(raw)
            chunks = rag_service.segments_to_chunks(
                segments, splitter_type, chunk_size, chunk_overlap, splitter_regex
            )
            rag_service.index_chunks(db, doc, chunks)
            doc.chunk_count = len(chunks)
            doc.status = "indexed"
            meta = dict(doc.metadata_ or {})
            meta["error"] = None
            meta["loader"] = loader
            meta["splitter_type"] = splitter_type
            meta["splitter_regex"] = splitter_regex
            meta["chunk_size"] = chunk_size
            meta["chunk_overlap"] = chunk_overlap
            doc.metadata_ = meta
            kb = rag_service.get_kb(db, kb_id)
            kb.loader = loader
            kb.splitter_type = splitter_type
            kb.splitter_regex = splitter_regex
            kb.chunk_size = chunk_size
            kb.chunk_overlap = chunk_overlap
            db.commit()
            logger.info(f"[upload] doc {doc_id} indexed, chunks={len(chunks)} (loader={loader})")
        except Exception as e:
            logger.exception(f"[upload] indexing failed for doc {doc_id}")
            doc.status = "failed"
            doc.metadata_ = {"error": str(e)}
            db.commit()
    finally:
        try:
            os.remove(fpath)
        except OSError:
            pass
        db.close()


@router.post("/kbs/{kb_id}/upload", summary="上传文档(异步: 立即返回 doc_id)")
async def upload_doc(
    kb_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    loader: str = Form("auto", description="加载器: text/markdown/auto"),
    splitter_type: str = Form("sentence", description="token/sentence/regex/semantic"),
    splitter_regex: str = Form("", description="regex 分块的分隔正则"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required_enabled),
):
    _check_kb(db, kb_id, user)
    raw = await file.read()
    if not raw:
        raise ErrBadRequest("空文件")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise AppException(ErrorCode.UPLOAD_FAILED,
                           f"文件过大({len(raw)/1024/1024:.1f}MB),上限{settings.MAX_UPLOAD_MB}MB",
                           http_status=413)
    _validate_magic(raw, file.filename or "")

    if loader == "auto":
        loader = detect_by_filename(file.filename or "")
    get_loader(loader)

    upload_dir = str(settings.upload_dir_abs)
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    fpath = os.path.join(upload_dir, safe_name)
    with open(fpath, "wb") as f:
        f.write(raw)

    doc = Document(
        kb_id=kb_id, name=file.filename or "untitled",
        display_name=file.filename or "untitled",
        file_path=fpath, file_size=len(raw),
        content_type=file.content_type or "text/plain",
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background.add_task(
        _index_task, doc.id, kb_id, fpath, raw,
        loader, splitter_type, splitter_regex, chunk_size, chunk_overlap,
    )

    return ok({
        "document_id": doc.id, "filename": doc.name, "display_name": doc.display_name,
        "status": "processing", "loader": loader,
        "splitter_type": splitter_type, "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
    }, msg="上传成功,后台正在分块向量化")


@router.post("/query", summary="检索知识库")
def query_docs(body: QueryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    # 查询前校验该 KB 属于当前用户或为公开 (KB 目前无公开字段,按 owner 校验)
    _check_kb(db, body.kb_id, user)
    return ok(rag_service.query_documents(db, body))


class BatchQueryIn(BaseModel):
    queries: list[QueryIn]


@router.post("/query/batch", summary="批量检索多个 query (带缓存)")
def batch_query_docs(body: BatchQueryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    if len(body.queries) > 20:
        from app.core.exceptions import ErrBadRequest
        raise ErrBadRequest("单次批量检索上限 20 个 query")
    for q in body.queries:
        _check_kb(db, q.kb_id, user)
    return ok(rag_service.batch_query(db, body.queries))


@router.post("/kbs/{kb_id}/load", summary="手动预热/加载向量集合到内存 (admin)")
def load_kb_collection(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user_required_enabled)):
    if not is_admin(user):
        raise ErrForbidden("仅管理员可手动加载集合")
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        from app.core.exceptions import ErrNotFound
        raise ErrNotFound("知识库不存在")
    from app.services import vector_store
    ok_flag = vector_store.ensure_loaded(kb_id)
    return ok({"loaded": ok_flag, "kb_id": kb_id})
