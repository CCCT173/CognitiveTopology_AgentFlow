"""
Embedding & Rerank 封装
支持 provider:
  - ark:     ARK 火山方舟多模态 embedding (doubao-embedding-vision 等),支持文字/图片/视频
  - giteeai: GiteeAI Qwen3-Embedding-8B (文字)
  - fake:    确定性伪向量(离线兜底)

多模态:
  embed_texts(texts)                 纯文本批量
  embed_image(image_path_or_url)      单张图片
  embed_video(video_path_or_url)      单个视频(ARK 会自动抽帧)
  embed_multimodal(inputs)           混合输入 list[ {"type":"text|image_url|video_url","text"/"image_url"/"video_url":...} ]

注意:
  ARK /v1/embeddings 接口对多模态的入参格式:
    input = [ {"type":"text",      "text":"..."},
              {"type":"image_url", "image_url": {"url":"data:image/png;base64,xxx"}} ]
  image 支持本地路径(自动转 base64 data-url) 或 http(s) URL。
  视频同理,ARK 接受 video_url 或 file 上传(这里先支持 http URL,文件后续再补)。
"""
from __future__ import annotations
import base64
import hashlib
import os
import random
from functools import lru_cache
from typing import Sequence, Any

from openai import OpenAI

from app.core.config import settings
from app.core.logger import logger


# ---------- client ----------
@lru_cache(maxsize=2)
def _client(provider: str) -> OpenAI:
    if provider == "ark":
        return OpenAI(api_key=settings.ARK_API_KEY, base_url=settings.ARK_BASE_URL,
                      timeout=30.0, max_retries=2)
    if provider == "giteeai":
        return OpenAI(api_key=settings.GITEEAI_API_KEY, base_url=settings.GITEEAI_BASE_URL,
                      timeout=30.0, max_retries=2)
    raise ValueError(f"未知 embedding provider: {provider}")


def _model_name() -> str:
    if settings.EMBEDDING_PROVIDER == "ark":
        return settings.ARK_EMBEDDING_MODEL
    if settings.EMBEDDING_PROVIDER == "giteeai":
        return settings.EMBEDDING_MODEL_NAME
    return ""


# ---------- 对外 ----------
def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """批量文本向量化。"""
    if not texts:
        return []
    if settings.EMBEDDING_PROVIDER == "fake":
        return [_fake_vec(t) for t in texts]
    try:
        resp = _client(settings.EMBEDDING_PROVIDER).embeddings.create(
            model=_model_name(), input=list(texts),
        )
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]
    except Exception as e:
        logger.warning(f"embed_texts 调用失败({settings.EMBEDDING_PROVIDER}),降级fake: {e}")
        return [_fake_vec(t) for t in texts]


def embed_query(text: str) -> list[float]:
    """单条文本 query 向量化。"""
    return embed_texts([text])[0]


def embed_image(image: str) -> list[float]:
    """
    单张图片向量化。image 可以是 http(s) URL 或本地文件路径。
    仅 ARK / giteeai(若支持视觉) 生效; fake 时返回确定性向量。
    """
    item = _to_image_item(image)
    return embed_multimodal([item])[0]


def embed_video(video_url: str) -> list[float]:
    """
    单个视频向量化。video_url 需 http(s) URL (ARK 服务端拉取+抽帧)。
    本地文件上传待实现。
    """
    item = {"type": "video_url", "video_url": {"url": video_url}}
    return embed_multimodal([item])[0]


def _normalize_multimodal_inputs(inputs: list[dict]) -> list[dict]:
    """ARK / 标准 OpenAI 兼容: image_url 字段接受字符串 url 或 {"url": ...}"""
    out = []
    for it in inputs:
        t = it.get("type")
        if t == "image_url":
            iu = it.get("image_url")
            if isinstance(iu, dict):
                url = iu.get("url", "")
            else:
                url = str(iu)
            # ARK 接受 {type:"image_url", image_url:"<url>"} (字符串) 或嵌套 dict; 尝试最宽松格式
            out.append({"type": "image_url", "image_url": url})
        elif t == "video_url":
            vu = it.get("video_url")
            url = vu.get("url", "") if isinstance(vu, dict) else str(vu)
            out.append({"type": "video_url", "video_url": url})
        else:
            out.append({"type": "text", "text": it.get("text", "")})
    return out


def embed_multimodal(inputs: list[dict]) -> list[list[float]]:
    if not inputs:
        return []
    if settings.EMBEDDING_PROVIDER == "fake":
        return [_fake_vec(str(i)) for i in inputs]
    try:
        norm = _normalize_multimodal_inputs(inputs)
        resp = _client(settings.EMBEDDING_PROVIDER).embeddings.create(
            model=_model_name(), input=norm,
        )
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]
    except Exception as e:
        logger.warning(f"embed_multimodal 调用失败,降级fake: {e}")
        return [_fake_vec(str(i)) for i in inputs]


# ---------- helpers ----------
def _to_image_item(image: str) -> dict:
    """本地路径 -> data-url; URL 原样。"""
    if image.startswith(("http://", "https://", "data:")):
        url = image
    else:
        url = _local_image_to_data_url(image)
    return {"type": "image_url", "image_url": {"url": url}}


def _local_image_to_data_url(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"图片文件不存在: {path}")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(ext, "png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


def _fake_vec(text: str) -> list[float]:
    dim = settings.EMBEDDING_DIM
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    vec = [rng.uniform(-1, 1) for _ in range(dim)]
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


# ---------- Rerank ----------
def _giteeai_rerank(query: str, documents: list[str], top_n: int | None) -> list[tuple[int, float]]:
    """调用 GiteeAI /v1/rerank (Qwen3-Reranker-4B)"""
    if not settings.GITEEAI_API_KEY:
        raise ValueError("GITEEAI_API_KEY 未配置,无法调用 reranker")
    import requests
    resp = requests.post(
        f"{settings.GITEEAI_BASE_URL.rstrip('/')}/rerank",
        headers={"Authorization": f"Bearer {settings.GITEEAI_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": settings.RERANKER_MODEL_NAME,
              "query": query, "documents": documents,
              "top_n": top_n or len(documents)},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [(item["index"], float(item.get("relevance_score", item.get("score", 0.0))))
            for item in data.get("results", [])]


def _bm25_rerank(query: str, documents: list[str], top_n: int | None) -> list[tuple[int, float]]:
    """BM25-lite 离线兜底"""
    import re
    def tok(t: str) -> list[str]:
        return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", t.lower())
    q_tokens = set(tok(query))
    scored = []
    for i, doc in enumerate(documents):
        d_tokens = tok(doc)
        if not q_tokens or not d_tokens:
            scored.append((i, 0.0)); continue
        overlap = sum(1 for t in d_tokens if t in q_tokens)
        score = overlap / (len(d_tokens) ** 0.5 + 1)
        scored.append((i, float(score)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n] if top_n else scored


def rerank(query: str, documents: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
    """对文档进行重排, 返回 [(原索引, 分数), ...] 按分数降序"""
    if not documents:
        return []
    if settings.RERANKER_PROVIDER == "giteeai":
        try:
            return _giteeai_rerank(query, documents, top_n)
        except Exception as e:
            logger.warning(f"GiteeAI rerank 调用失败,降级 BM25: {e}")
    return _bm25_rerank(query, documents, top_n)
