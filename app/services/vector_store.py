"""
向量库封装 - 支持 Milvus Lite (单文件本地) 与 Milvus Server
chunk.id 直接作为向量主键,删除 chunk 时同步删向量
每个知识库对应一个 collection: kb_{kb_id}
"""
import os
from typing import Iterable
from pymilvus import MilvusClient, DataType
from pymilvus.milvus_client import IndexParams

from app.core.config import settings
from app.core.logger import logger


_client: MilvusClient | None = None


def get_client() -> MilvusClient:
    """获取/初始化 Milvus 客户端(单例)"""
    global _client
    if _client is None:
        if settings.VECTOR_STORE == "milvus_lite":
            # 保证数据目录存在
            db_path = settings.milvus_db_abs
            db_dir = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(db_dir, exist_ok=True)
            uri = db_path
            logger.info(f"Milvus Lite 初始化,数据文件: {os.path.abspath(uri)}")
        else:
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            logger.info(f"连接 Milvus Server: {uri}")
        _client = MilvusClient(uri=uri)
    return _client


def collection_name(kb_id: int) -> str:
    return f"kb_{kb_id}"


def ensure_collection(kb_id: int, dim: int | None = None):
    """确保知识库对应的 collection 存在(不存在则创建)"""
    client = get_client()
    col = collection_name(kb_id)
    dim = dim or settings.EMBEDDING_DIM
    if client.has_collection(col):
        return
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(field_name="document_id", datatype=DataType.INT64)
    schema.add_field(field_name="chunk_index", datatype=DataType.INT32)
    index_params = IndexParams()
    index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(col, schema=schema, index_params=index_params)
    logger.info(f"已创建向量集合 {col} (dim={dim})")


def drop_collection(kb_id: int):
    """删除知识库时级联删除向量集合。
    Windows 上 milvus-lite 的 manifest.json.tmp -> manifest.json 原子重命名偶发失败,
    通过重试 + 失败后手动清理目录兜底。"""
    client = get_client()
    col = collection_name(kb_id)
    if not client.has_collection(col):
        return
    last_err = None
    for attempt in range(3):
        try:
            client.drop_collection(col)
            logger.info(f"已删除向量集合 {col}")
            return
        except Exception as e:
            last_err = e
            # 清理可能残留的 tmp 文件
            _cleanup_lite_tmp(col)
            import time; time.sleep(0.1 * (attempt + 1))
    # drop 一直失败,手动删除 milvus-lite 的 collection 目录兜底
    try:
        _manual_remove_collection(col)
        # 刷新客户端缓存
        if hasattr(client, "_refresh_collections"):
            try:
                client._refresh_collections()
            except Exception:
                pass
        if not client.has_collection(col):
            logger.info(f"已手动清理向量集合 {col}")
            return
    except Exception as e:
        logger.warning(f"手动清理 {col} 失败: {e}")
    logger.warning(f"删除向量集合 {col} 时出错(可忽略): {last_err}")


def _cleanup_lite_tmp(col: str):
    """删除 milvus-lite manifest.json.tmp 残留文件"""
    if settings.VECTOR_STORE != "milvus_lite":
        return
    try:
        db_path = settings.milvus_db_abs
        col_dir = os.path.join(db_path, "collections", col)
        tmp = os.path.join(col_dir, "manifest.json.tmp")
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass


def _manual_remove_collection(col: str):
    """直接删除 milvus-lite 的 collection 目录,用于 drop_collection 失败兜底"""
    import shutil
    if settings.VECTOR_STORE != "milvus_lite":
        return
    db_path = settings.milvus_db_abs
    col_dir = os.path.join(db_path, "collections", col)
    if os.path.isdir(col_dir):
        shutil.rmtree(col_dir, ignore_errors=True)


def insert_chunks(kb_id: int, records: list[dict]):
    """
    批量插入分块向量
    records: [{id(chunk_id), vector(list[float]), document_id, chunk_index}]
    """
    client = get_client()
    ensure_collection(kb_id)
    if not records:
        return
    col = collection_name(kb_id)
    try:
        client.insert(col, records)
    except Exception as e:
        msg = str(e).lower()
        if "load" in msg or "not loaded" in msg:
            try:
                client.load_collection(col)
            except Exception:
                pass
            client.insert(col, records)
        else:
            raise


def delete_chunks(kb_id: int, chunk_ids: Iterable[int]):
    """按 chunk_id 删向量(单个chunk或文档级联用)"""
    client = get_client()
    col = collection_name(kb_id)
    ids = list(chunk_ids)
    if not ids or not client.has_collection(col):
        return
    client.delete(col, ids)


def delete_by_document(kb_id: int, document_id: int):
    """删除某文档所有向量(删文档时调用)"""
    client = get_client()
    col = collection_name(kb_id)
    if not client.has_collection(col):
        return
    client.delete(col, filter=f"document_id == {document_id}")


def search(kb_id: int, query_vector: list[float], top_k: int = 5, hybrid: bool = True):
    """
    向量检索, 返回 [(chunk_id, document_id, score)]
    hybrid 参数预留,目前走纯向量检索,后续可加 BM25/关键词做融合
    """
    client = get_client()
    col = collection_name(kb_id)
    if not client.has_collection(col):
        return []
    # 自愈：collection 存在但未 load 到内存时，Milvus 会抛 "collection not loaded"
    # 这里做一次 load + 重试, 避免长期 "released" 导致检索始终为空
    try:
        return _do_search(client, col, query_vector, top_k)
    except Exception as e:
        msg = str(e).lower()
        if "load" in msg or "not loaded" in msg or "released" in msg:
            logger.warning(f"集合 {col} 未加载，尝试 load_collection 自愈: {e}")
            try:
                client.load_collection(col)
            except Exception as le:
                logger.warning(f"load_collection({col}) 失败: {le}")
            try:
                return _do_search(client, col, query_vector, top_k)
            except Exception as e2:
                logger.error(f"自愈后再次检索失败: {e2}")
                return []
        logger.error(f"向量检索失败 {col}: {e}")
        return []


def _do_search(client, col, query_vector, top_k):
    res = client.search(
        collection_name=col,
        data=[query_vector],
        limit=top_k,
        search_params={"metric_type": "COSINE", "params": {}},
        output_fields=["document_id", "chunk_index"],
    )
    hits = []
    for h in res[0]:
        hits.append({
            "chunk_id": h["id"],
            "document_id": h["entity"].get("document_id"),
            "chunk_index": h["entity"].get("chunk_index"),
            "score": float(h["distance"]),
        })
    return hits


def ensure_loaded(kb_id: int):
    """外部可显式触发集合 load（如查询前预热）"""
    client = get_client()
    col = collection_name(kb_id)
    if not client.has_collection(col):
        return False
    try:
        client.load_collection(col)
        return True
    except Exception as e:
        logger.warning(f"load_collection({col}) 失败: {e}")
        return False
