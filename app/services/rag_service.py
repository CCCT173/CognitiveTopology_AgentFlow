"""
RAG 知识库/文档/Chunk CRUD + 向量检索
- chunk 增删改查 会同步 Milvus 向量 (改内容时重新 embed,删时删向量)
- splitter 支持 token/sentence/regex/semantic(semantic 预留,当前按 sentence)
- loader: text/pdf(预留pypdf)/docx/markdown/image(OCR预留)
"""
import re
import time
import hashlib
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.rag import KnowledgeBase, Document, Chunk
from app.schemas.rag import KBCreate, KBUpdate, QueryIn, ChunkCreate, ChunkUpdate, DocumentUpdate
from app.core.exceptions import ErrNotFound, ErrConflict, ErrBadRequest
from app.services import vector_store
from app.services.embeddings import embed_texts, embed_query, rerank
from app.core.logger import logger


# ============ 检索缓存 (进程内 LRU, TTL 60s) ============
_QUERY_CACHE: dict[str, tuple[float, list]] = {}
_CACHE_MAX = 512
_CACHE_TTL = 60.0


def _cache_get(key: str):
    item = _QUERY_CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if time.time() - ts > _CACHE_TTL:
        _QUERY_CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val):
    if len(_QUERY_CACHE) >= _CACHE_MAX:
        # 淘汰最早的 20%
        keys = sorted(_QUERY_CACHE, key=lambda k: _QUERY_CACHE[k][0])[:_CACHE_MAX // 5]
        for k in keys:
            _QUERY_CACHE.pop(k, None)
    _QUERY_CACHE[key] = (time.time(), val)


def query_cache_clear():
    """文档/chunk 变更时清空缓存"""
    _QUERY_CACHE.clear()


# ============ KB ============
def list_kbs(db: Session, owner_id: int | None = None) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase)
    if owner_id is not None:
        stmt = stmt.where(KnowledgeBase.created_by == owner_id)
    kbs = list(db.scalars(stmt).all())
    # 统计每个 kb 的文档数 + 总切块数
    doc_counts = dict(db.execute(
        select(Document.kb_id, func.count(Document.id)).group_by(Document.kb_id)
    ).all())
    chunk_counts = dict(db.execute(
        select(Document.kb_id, func.sum(Document.chunk_count))
        .group_by(Document.kb_id)
    ).all())
    for k in kbs:
        setattr(k, "_doc_count", doc_counts.get(k.id, 0))
        setattr(k, "_total_chunks", int(chunk_counts.get(k.id, 0) or 0))
    return kbs


def kb_stats(db: Session, kb_id: int) -> dict:
    """返回某知识库的文档数/总切块数"""
    doc_count = db.scalar(select(func.count(Document.id)).where(Document.kb_id == kb_id)) or 0
    total_chunks = db.scalar(select(func.coalesce(func.sum(Document.chunk_count), 0)).where(Document.kb_id == kb_id)) or 0
    return {"document_count": int(doc_count), "total_chunks": int(total_chunks)}


def get_kb(db: Session, kb_id: int) -> KnowledgeBase:
    obj = db.get(KnowledgeBase, kb_id)
    if not obj:
        raise ErrNotFound(f"知识库 {kb_id} 不存在")
    stats = kb_stats(db, kb_id)
    setattr(obj, "_doc_count", stats["document_count"])
    setattr(obj, "_total_chunks", stats["total_chunks"])
    return obj


def create_kb(db: Session, body: KBCreate, user_id: int | None = None) -> KnowledgeBase:
    if db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == body.name)):
        raise ErrConflict(f"知识库 '{body.name}' 已存在")
    data = body.model_dump()
    obj = KnowledgeBase(**data, created_by=user_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    vector_store.ensure_collection(obj.id)
    return obj


def update_kb(db: Session, kb_id: int, body: KBUpdate) -> KnowledgeBase:
    obj = get_kb(db, kb_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def set_kb_icon(db: Session, kb_id: int, icon_url: str) -> KnowledgeBase:
    obj = get_kb(db, kb_id)
    obj.icon_url = icon_url
    db.commit()
    db.refresh(obj)
    return obj


def delete_kb(db: Session, kb_id: int) -> None:
    obj = get_kb(db, kb_id)
    db.delete(obj)
    db.commit()
    vector_store.drop_collection(kb_id)


# ============ 文档 ============
def list_documents(db: Session, kb_id: int) -> list[Document]:
    get_kb(db, kb_id)
    return list(db.scalars(select(Document).where(Document.kb_id == kb_id)).all())


def get_document(db: Session, doc_id: int) -> Document:
    obj = db.get(Document, doc_id)
    if not obj:
        raise ErrNotFound(f"文档 {doc_id} 不存在")
    return obj


def update_document(db: Session, doc_id: int, body: DocumentUpdate) -> Document:
    obj = get_document(db, doc_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_document(db: Session, doc_id: int) -> None:
    obj = get_document(db, doc_id)
    kb_id = obj.kb_id
    db.delete(obj)
    db.commit()
    vector_store.delete_by_document(kb_id, doc_id)


# ============ Chunk ============
def list_chunks(db: Session, doc_id: int) -> list[Chunk]:
    get_document(db, doc_id)
    return list(db.scalars(
        select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index.asc(), Chunk.id.asc())
    ).all())


def create_chunk(db: Session, doc_id: int, body: ChunkCreate) -> Chunk:
    doc = get_document(db, doc_id)
    # 确定 chunk_index
    if body.chunk_index is not None:
        idx = body.chunk_index
    else:
        # 追加到末尾: 取当前 max index + 1
        max_idx = db.scalar(select(func.max(Chunk.chunk_index)).where(Chunk.document_id == doc_id))
        idx = (max_idx or -1) + 1
    chunk = Chunk(
        document_id=doc_id, chunk_index=idx,
        content=body.content, token_count=len(body.content),
        metadata_=body.metadata_,
    )
    db.add(chunk)
    db.flush()
    # 向量化
    vec = embed_texts([body.content])[0]
    vector_store.insert_chunks(doc.kb_id, [{
        "id": chunk.id, "vector": vec,
        "document_id": doc.id, "chunk_index": idx,
    }])
    doc.chunk_count = doc.chunk_count + 1
    db.commit()
    db.refresh(chunk)
    return chunk


def update_chunk(db: Session, chunk_id: int, body: ChunkUpdate) -> Chunk:
    obj = db.get(Chunk, chunk_id)
    if not obj:
        raise ErrNotFound(f"chunk {chunk_id} 不存在")
    doc = get_document(db, obj.document_id)

    need_reembed = False
    if body.content is not None and body.content != obj.content:
        obj.content = body.content
        obj.token_count = len(body.content)
        need_reembed = True
    if body.chunk_index is not None:
        obj.chunk_index = body.chunk_index
        # index 变了也要重新 upsert Milvus
        need_reembed = True
    if body.metadata_ is not None:
        obj.metadata_ = body.metadata_

    if need_reembed:
        vec = embed_texts([obj.content])[0]
        # 简化: 先删再插(Milvus upsert 也支持,但 Lite 版本兼容性不一)
        try:
            vector_store.delete_chunks(doc.kb_id, [obj.id])
        except Exception:
            pass
        vector_store.insert_chunks(doc.kb_id, [{
            "id": obj.id, "vector": vec,
            "document_id": doc.id, "chunk_index": obj.chunk_index,
        }])
    db.commit()
    db.refresh(obj)
    return obj


def delete_chunk(db: Session, chunk_id: int) -> None:
    obj = db.get(Chunk, chunk_id)
    if not obj:
        raise ErrNotFound(f"chunk {chunk_id} 不存在")
    doc = get_document(db, obj.document_id)
    kb_id = doc.kb_id
    db.delete(obj)
    vector_store.delete_chunks(kb_id, [chunk_id])
    doc.chunk_count = max(0, doc.chunk_count - 1)
    db.commit()


# ============ 分块 ============
def split_text(text: str, splitter: str, chunk_size: int, overlap: int, regex: str = "") -> list[str]:
    """按 splitter 类型切分文本"""
    text = text.strip()
    if not text:
        return []
    if splitter == "token":
        return [text[i:i + chunk_size] for i in range(0, len(text), max(1, chunk_size - overlap))]
    if splitter == "regex":
        if not regex:
            raise ErrBadRequest("splitter=regex 时必须提供 splitter_regex")
        try:
            parts_raw = re.split(f"({regex})", text)
            parts = []
            buf = parts_raw[0].strip() if parts_raw else ""
            if buf: parts.append(buf)
            for i in range(1, len(parts_raw), 2):
                sep = parts_raw[i]
                body = parts_raw[i + 1] if i + 1 < len(parts_raw) else ""
                seg = (sep + body).strip()
                if seg: parts.append(seg)
        except re.error as e:
            raise ErrBadRequest(f"非法正则: {e}")
        return _merge_parts(parts, chunk_size)
    if splitter == "semantic":
        return _split_semantic(text, chunk_size)
    # sentence(默认)
    sents = [s.strip() for s in re.split(r"[。！？!?\.\!\?\n]+", text) if s.strip()]
    return _merge_parts(sents, chunk_size)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return dot / (na * nb)


def _split_semantic(text: str, chunk_size: int, threshold: float = 0.5) -> list[str]:
    """
    语义分块:
      1. 按句子切
      2. 对每句 embed
      3. 相邻句子余弦相似度 >= threshold 合并;
         已积累内容长度 >= chunk_size*0.5 且相似度骤降时断块
    """
    from app.services.embeddings import embed_texts
    sents = [s.strip() for s in re.split(r"[。！？!?\.\!\?\n]+", text) if s.strip()]
    if not sents:
        return []
    if len(sents) == 1:
        return _merge_parts(sents, chunk_size)
    vecs = embed_texts(sents)
    chunks, buf, buf_len = [], sents[0], len(sents[0])
    for i in range(1, len(sents)):
        sim = _cosine(vecs[i - 1], vecs[i])
        new_len = buf_len + 1 + len(sents[i])
        # 策略: 相似度低 且 缓冲已积累到 chunk_size 一半以上 -> 断块
        split_here = (sim < threshold and buf_len >= chunk_size * 0.3) or new_len > chunk_size
        if split_here:
            chunks.append(buf)
            buf = sents[i]; buf_len = len(sents[i])
        else:
            buf = buf + "。" + sents[i]; buf_len = new_len
    if buf:
        chunks.append(buf)
    # 若分块过碎(每块都很小),再按 chunk_size 合并
    return _merge_parts(chunks, chunk_size) or [text]


def _merge_parts(parts: list[str], chunk_size: int) -> list[str]:
    chunks, buf = [], ""
    for s in parts:
        if len(buf) + len(s) + 1 <= chunk_size:
            buf = (buf + "。" + s) if buf else s
        else:
            if buf:
                chunks.append(buf)
            # 单条超长则硬切
            while len(s) > chunk_size:
                chunks.append(s[:chunk_size])
                s = s[chunk_size:]
            buf = s
    if buf:
        chunks.append(buf)
    return chunks


# ============ 写入(给上传用) ============
def index_chunks(db: Session, doc: Document, chunks: list[dict]):
    """
    批量入库 chunks 到 MySQL + Milvus。
    chunks: list[{"content": str, "meta": dict}]
        meta 必须包含 type ("text"|"image"), 可选 page/image_data_url
        - 对 image 类型, content 是占位文本, 向量通过 embed_image(data_url) 生成
    """
    if not chunks:
        return
    chunk_objs = []
    vec_inputs_text: list[tuple[int, str]] = []   # (idx, text)
    vec_inputs_image: list[tuple[int, str]] = []  # (idx, data_url)

    for idx, item in enumerate(chunks):
        c = Chunk(
            document_id=doc.id,
            chunk_index=idx,
            content=item["content"],
            token_count=len(item["content"]),
            metadata_=item.get("meta", {}),
        )
        db.add(c); chunk_objs.append(c)
    db.flush()

    # 分类型批量 embed
    for i, c in enumerate(chunk_objs):
        meta = chunks[i].get("meta", {})
        if meta.get("type") == "image":
            vec_inputs_image.append((i, meta["image_data_url"]))
        else:
            vec_inputs_text.append((i, c.content))

    vectors: list[list[float] | None] = [None] * len(chunk_objs)
    if vec_inputs_text:
        from app.services.embeddings import embed_texts
        idxs, texts = zip(*vec_inputs_text)
        vecs = embed_texts(list(texts))
        for i, v in zip(idxs, vecs):
            vectors[i] = v
    if vec_inputs_image:
        from app.services.embeddings import embed_image
        for i, url in vec_inputs_image:
            try:
                vectors[i] = embed_image(url)
            except Exception as e:
                logger.warning(f"图片 embed 失败 chunk {chunk_objs[i].id}: {e}")
                # 失败兜底用占位文本向量
                vectors[i] = embed_texts([chunk_objs[i].content])[0]

    records = []
    for c, vec in zip(chunk_objs, vectors):
        if vec is None:
            continue
        records.append({
            "id": c.id, "vector": vec,
            "document_id": doc.id, "chunk_index": c.chunk_index,
        })
    vector_store.insert_chunks(doc.kb_id, records)


def segments_to_chunks(segments, splitter: str, chunk_size: int, overlap: int, regex: str = "") -> list[dict]:
    """
    把 Loader 返回的 Segment 列表切成 index_chunks 需要的 chunk dict 列表:
      - text Segment 先按选定 splitter 切分, 每个子段一个 chunk
      - image Segment 直接作为独立 chunk (content 是占位, meta.image_data_url 是 data-url)
    """
    from app.services.loaders import Segment
    out: list[dict] = []
    for seg in segments:
        if seg.type == "image":
            out.append({
                "content": f"[IMAGE 第{seg.page}页]",
                "meta": {"type": "image", "page": seg.page, "image_data_url": seg.content},
            })
        else:
            text_chunks = split_text(seg.content, splitter, chunk_size, overlap, regex)
            for t in text_chunks:
                out.append({
                    "content": t,
                    "meta": {"type": "text", "page": seg.page},
                })
    return out


# ============ 检索 ============
def query_documents(db: Session, body: QueryIn) -> list[dict]:
    cache_key = hashlib.md5(
        f"{body.kb_id}|{body.query}|{body.top_k}|{body.rerank}|{body.return_content}".encode()
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    kb = get_kb(db, body.kb_id)
    qvec = embed_query(body.query)
    hits = vector_store.search(kb.id, qvec, top_k=body.top_k)
    if not hits:
        _cache_set(cache_key, [])
        return []
    chunk_ids = [h["chunk_id"] for h in hits]
    chunks = db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    chunk_map = {c.id: c for c in chunks}
    doc_ids = {c.document_id for c in chunks}
    docs = db.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
    doc_map = {d.id: d for d in docs}

    candidates = []
    for h in hits:
        c = chunk_map.get(h["chunk_id"])
        d = doc_map.get(h["document_id"]) if c else None
        if not c:
            continue
        dn = d.display_name or d.name if d else ""
        candidates.append({
            "chunk_id": c.id,
            "document_id": c.document_id,
            "document_name": dn,
            "content": c.content,
            "chunk_index": c.chunk_index,
            "vector_score": float(h["score"]),
        })

    if body.rerank and len(candidates) > 1:
        docs_text = [c["content"] for c in candidates]
        ranked = rerank(body.query, docs_text, top_n=len(candidates))
        result = []
        for orig_idx, rscore in ranked:
            item = dict(candidates[orig_idx])
            item["rerank_score"] = round(rscore, 4)
            item["score"] = round(rscore, 4)
            result.append(item)
        candidates = result
    else:
        for c in candidates:
            c["score"] = round(c["vector_score"], 4)

    if not body.return_content:
        for c in candidates:
            c.pop("content", None)

    _cache_set(cache_key, candidates)
    return candidates


def batch_query(db: Session, queries: list[QueryIn]) -> list[list[dict]]:
    """批量检索 (多个 query 顺序执行, 带缓存)"""
    return [query_documents(db, q) for q in queries]
