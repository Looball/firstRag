"""Milvus dense/sparse 混合检索流水线。"""

import logging
import math
from collections.abc import Sequence
from contextvars import ContextVar
from hashlib import sha256
from threading import RLock
from time import monotonic
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.core.config import (
    SPARSE_ENCODER_MAX_LENGTH,
    SPARSE_ENCODER_MODEL,
    SPARSE_ENCODER_REVISION,
)
from app.core.observability import log_exception_event
from app.services import cache_service
from app.services.retrieval.reranker import (
    DEFAULT_RERANKER_MAX_LENGTH,
    DEFAULT_RERANKER_MODEL,
    get_reranker,
)
from app.services.sparse_encoder_client import SparseEncoderClient
from app.services.vectors.embedding_model import (
    create_embedding_model,
    get_embedding_cache_identity,
)
from app.services.vectors.vector_store_factory import get_vector_store

logger = logging.getLogger(__name__)

QUERY_EMBEDDING_CACHE_TTL_SECONDS = 300.0
QUERY_SPARSE_EMBEDDING_CACHE_TTL_SECONDS = 300.0
MAX_CHILD_CANDIDATES_PER_PARENT = 2
_QUERY_EMBEDDING_CACHE: dict[
    tuple[str, str, str, str, str],
    tuple[float, list[float]],
] = {}
_QUERY_EMBEDDING_CACHE_LOCK = RLock()
_QUERY_SPARSE_EMBEDDING_CACHE: dict[
    tuple[str, str, str, str, str],
    tuple[float, dict[int, float]],
] = {}
_QUERY_SPARSE_EMBEDDING_CACHE_LOCK = RLock()

_RETRIEVAL_DIAGNOSTICS: ContextVar[dict[str, Any] | None] = ContextVar(
    "retrieval_diagnostics",
    default=None,
)


def reset_retrieval_diagnostics() -> None:
    """初始化当前请求的检索诊断信息。"""
    _RETRIEVAL_DIAGNOSTICS.set({
        "retrieval_mode": "milvus_dense_sparse",
        "dense_degraded": False,
        "dense_errors": [],
        "sparse_degraded": False,
        "sparse_errors": [],
        "hybrid_degraded": False,
        "hybrid_errors": [],
        "query_embedding_cache_hit": False,
        "query_embedding_cache_key": "",
        "query_embedding_cache_source": "provider",
        "query_embedding_cache_fallback_reason": None,
        "query_embedding_cache_ttl_seconds": QUERY_EMBEDDING_CACHE_TTL_SECONDS,
        "query_sparse_embedding_cache_hit": False,
        "query_sparse_embedding_cache_key": "",
        "query_sparse_embedding_cache_source": "encoder",
        "query_sparse_embedding_cache_fallback_reason": None,
        "query_sparse_embedding_cache_ttl_seconds": (
            QUERY_SPARSE_EMBEDDING_CACHE_TTL_SECONDS
        ),
        "dense_count": 0,
        "sparse_count": 0,
        "hybrid_count": 0,
        "fused_count": 0,
        "reranked_count": 0,
        "parent_count": 0,
        "parent_context_degraded": False,
        "parent_context_errors": [],
        "retrieval_sources": [],
        "timing": {},
    })


def get_retrieval_diagnostics() -> dict[str, Any] | None:
    """读取当前请求最近一次混合检索产生的诊断信息。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return None
    return dict(diagnostics)


def update_retrieval_diagnostics(**values: Any) -> None:
    """更新当前请求的检索诊断信息。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return
    diagnostics.update(values)


def add_dense_diagnostic_error(message: str) -> None:
    """记录 dense query 或 search 单路降级。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return
    diagnostics["dense_degraded"] = True
    diagnostics.setdefault("dense_errors", []).append(message)


def add_sparse_diagnostic_error(message: str) -> None:
    """记录 sparse query 或 search 单路降级。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return
    diagnostics["sparse_degraded"] = True
    diagnostics.setdefault("sparse_errors", []).append(message)


def add_hybrid_diagnostic_error(message: str) -> None:
    """记录 Milvus hybrid search 整体失败。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return
    diagnostics["hybrid_degraded"] = True
    diagnostics.setdefault("hybrid_errors", []).append(message)


def record_retrieval_timing(name: str, started_at: float) -> None:
    """记录当前请求检索阶段的耗时，单位为毫秒。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return

    timing = diagnostics.setdefault("timing", {})
    timing[f"{name}_ms"] = round((perf_counter() - started_at) * 1000, 2)


def normalize_query_embedding_cache_text(query: str) -> str:
    """归一化 query embedding 缓存 key 中的文本部分。"""
    return " ".join(query.strip().lower().split())


def build_query_embedding_cache_key(
    query: str,
    user_id: int,
) -> tuple[str, str, str, str, str]:
    """构造 query embedding 缓存 key。"""
    identity = get_embedding_cache_identity(user_id)
    return (
        *identity,
        normalize_query_embedding_cache_text(query),
    )


def build_query_embedding_redis_cache_key(
    cache_key: tuple[str, str, str, str, str],
) -> str:
    """构造 query embedding 的 Redis cache key。"""
    query_hash = sha256(cache_key[-1].encode("utf-8")).hexdigest()
    return cache_service.build_cache_key(
        "query_embedding",
        cache_key[0],
        cache_key[1],
        cache_key[2],
        cache_key[3],
        query_hash,
    )


def normalize_cached_query_embedding(value: Any) -> list[float] | None:
    """校验并规范化缓存中的 query embedding。"""
    if not isinstance(value, list):
        return None

    embedding: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        embedding.append(float(item))
    return embedding


def write_query_embedding_memory_cache(
    cache_key: tuple[str, str, str, str, str],
    embedding: list[float],
    now: float,
) -> None:
    """写入进程内 query embedding fallback 缓存。"""
    with _QUERY_EMBEDDING_CACHE_LOCK:
        _QUERY_EMBEDDING_CACHE[cache_key] = (
            now + QUERY_EMBEDDING_CACHE_TTL_SECONDS,
            list(embedding),
        )


def update_query_embedding_cache_diagnostics(
    *,
    hit: bool,
    cache_key: tuple[str, str, str, str, str],
    source: str,
    fallback_reason: str | None = None,
) -> None:
    """记录 query embedding 缓存诊断。"""
    update_retrieval_diagnostics(
        query_embedding_cache_hit=hit,
        query_embedding_cache_key=":".join(cache_key),
        query_embedding_cache_source=source,
        query_embedding_cache_fallback_reason=fallback_reason,
        query_dense_embedding_cache_hit=hit,
        query_dense_embedding_cache_key=":".join(cache_key),
        query_dense_embedding_cache_source=source,
        query_dense_embedding_cache_fallback_reason=fallback_reason,
    )


def clear_query_embedding_cache() -> None:
    """清空 dense/sparse query embedding 缓存，主要用于测试。"""
    with _QUERY_EMBEDDING_CACHE_LOCK:
        _QUERY_EMBEDDING_CACHE.clear()
    with _QUERY_SPARSE_EMBEDDING_CACHE_LOCK:
        _QUERY_SPARSE_EMBEDDING_CACHE.clear()
    cache_service.delete_cache_prefix(
        cache_service.build_cache_prefix("query_embedding"),
    )
    cache_service.delete_cache_prefix(
        cache_service.build_cache_prefix("query_sparse_embedding"),
    )


def get_query_embedding(query: str, user_id: int) -> list[float]:
    """读取或生成 query embedding，成功结果写入短 TTL 缓存。"""
    cache_key = build_query_embedding_cache_key(query, user_id)
    redis_key = build_query_embedding_redis_cache_key(cache_key)
    now = monotonic()
    memory_expired = False

    with _QUERY_EMBEDDING_CACHE_LOCK:
        cached = _QUERY_EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            expires_at, embedding = cached
            if expires_at > now:
                update_query_embedding_cache_diagnostics(
                    hit=True,
                    cache_key=cache_key,
                    source="memory",
                )
                return list(embedding)
            _QUERY_EMBEDDING_CACHE.pop(cache_key, None)
            memory_expired = True

    if memory_expired:
        cache_service.delete_cache_key(redis_key)
    redis_result = cache_service.get_json_cache(redis_key)
    if redis_result.hit:
        cached_embedding = normalize_cached_query_embedding(
            redis_result.value,
        )
        if cached_embedding is not None:
            write_query_embedding_memory_cache(
                cache_key,
                cached_embedding,
                now,
            )
            update_query_embedding_cache_diagnostics(
                hit=True,
                cache_key=cache_key,
                source="redis",
            )
            return cached_embedding

    fallback_reason = redis_result.fallback_reason

    update_query_embedding_cache_diagnostics(
        hit=False,
        cache_key=cache_key,
        source="provider",
        fallback_reason=fallback_reason,
    )
    embedding_model = create_embedding_model(user_id)
    embedding = list(embedding_model.embed_query(query))

    write_query_embedding_memory_cache(cache_key, embedding, now)
    set_result = cache_service.set_json_cache(
        redis_key,
        embedding,
        QUERY_EMBEDDING_CACHE_TTL_SECONDS,
    )
    if set_result.fallback_reason and not fallback_reason:
        update_query_embedding_cache_diagnostics(
            hit=False,
            cache_key=cache_key,
            source="provider",
            fallback_reason=set_result.fallback_reason,
        )

    return embedding


def build_query_sparse_embedding_cache_key(
    query: str,
    user_id: int,
) -> tuple[str, str, str, str, str]:
    """构造包含 BGE-M3 identity 与 max_length 的 sparse query cache key。"""
    query_hash = sha256(
        normalize_query_embedding_cache_text(query).encode("utf-8"),
    ).hexdigest()
    return (
        str(user_id),
        SPARSE_ENCODER_MODEL,
        SPARSE_ENCODER_REVISION,
        str(SPARSE_ENCODER_MAX_LENGTH),
        query_hash,
    )


def build_query_sparse_embedding_redis_cache_key(
    cache_key: tuple[str, str, str, str, str],
) -> str:
    """构造不包含 query 明文的 sparse Redis cache key。"""
    return cache_service.build_cache_key(
        "query_sparse_embedding",
        cache_key[0],
        cache_key[1],
        cache_key[2],
        cache_key[3],
        cache_key[-1],
    )


def normalize_cached_query_sparse_embedding(
    value: Any,
) -> dict[int, float] | None:
    """校验 Redis JSON 反序列化后的 sparse query vector。"""
    if not isinstance(value, dict) or not value:
        return None
    normalized: dict[int, float] = {}
    for raw_index, raw_weight in value.items():
        try:
            index = int(raw_index)
            weight = float(raw_weight)
        except (TypeError, ValueError):
            return None
        if index < 0 or weight < 0.0 or not math.isfinite(weight):
            return None
        normalized[index] = weight
    return normalized or None


def update_query_sparse_embedding_cache_diagnostics(
    *,
    hit: bool,
    cache_key: tuple[str, str, str, str, str],
    source: str,
    fallback_reason: str | None = None,
) -> None:
    """记录 sparse query cache 命中、模型身份和 Redis fallback。"""
    update_retrieval_diagnostics(
        query_sparse_embedding_cache_hit=hit,
        query_sparse_embedding_cache_key=":".join(cache_key),
        query_sparse_embedding_cache_source=source,
        query_sparse_embedding_cache_fallback_reason=fallback_reason,
    )


def get_query_sparse_embedding(query: str, user_id: int) -> dict[int, float]:
    """读取或生成 BGE-M3 query sparse vector，并写入双层短 TTL cache。"""
    cache_key = build_query_sparse_embedding_cache_key(query, user_id)
    redis_key = build_query_sparse_embedding_redis_cache_key(cache_key)
    now = monotonic()
    with _QUERY_SPARSE_EMBEDDING_CACHE_LOCK:
        cached = _QUERY_SPARSE_EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            expires_at, embedding = cached
            if expires_at > now:
                update_query_sparse_embedding_cache_diagnostics(
                    hit=True,
                    cache_key=cache_key,
                    source="memory",
                )
                return dict(embedding)
            _QUERY_SPARSE_EMBEDDING_CACHE.pop(cache_key, None)

    redis_result = cache_service.get_json_cache(redis_key)
    if redis_result.hit:
        cached_embedding = normalize_cached_query_sparse_embedding(
            redis_result.value,
        )
        if cached_embedding is not None:
            with _QUERY_SPARSE_EMBEDDING_CACHE_LOCK:
                _QUERY_SPARSE_EMBEDDING_CACHE[cache_key] = (
                    now + QUERY_SPARSE_EMBEDDING_CACHE_TTL_SECONDS,
                    dict(cached_embedding),
                )
            update_query_sparse_embedding_cache_diagnostics(
                hit=True,
                cache_key=cache_key,
                source="redis",
            )
            return cached_embedding

    update_query_sparse_embedding_cache_diagnostics(
        hit=False,
        cache_key=cache_key,
        source="encoder",
        fallback_reason=redis_result.fallback_reason,
    )
    embedding = SparseEncoderClient().encode_query(query)
    normalized_embedding = normalize_cached_query_sparse_embedding(embedding)
    if normalized_embedding is None:
        raise ValueError("Sparse encoder 返回了无效 query vector")
    with _QUERY_SPARSE_EMBEDDING_CACHE_LOCK:
        _QUERY_SPARSE_EMBEDDING_CACHE[cache_key] = (
            now + QUERY_SPARSE_EMBEDDING_CACHE_TTL_SECONDS,
            dict(normalized_embedding),
        )
    set_result = cache_service.set_json_cache(
        redis_key,
        normalized_embedding,
        QUERY_SPARSE_EMBEDDING_CACHE_TTL_SECONDS,
    )
    if set_result.fallback_reason and not redis_result.fallback_reason:
        update_query_sparse_embedding_cache_diagnostics(
            hit=False,
            cache_key=cache_key,
            source="encoder",
            fallback_reason=set_result.fallback_reason,
        )
    return normalized_embedding


def limit_child_candidates_by_parent(
    documents: Sequence[Document],
    max_children_per_parent: int = MAX_CHILD_CANDIDATES_PER_PARENT,
) -> list[Document]:
    """按 Milvus 融合顺序限制单个 parent 可进入 rerank 的 child 数量。"""
    if max_children_per_parent < 1:
        raise ValueError("max_children_per_parent 必须大于 0")
    parent_counts: dict[str, int] = {}
    limited: list[Document] = []
    for document in documents:
        parent_id = str(document.metadata.get("parent_id") or "")
        if not parent_id:
            continue
        count = parent_counts.get(parent_id, 0)
        if count >= max_children_per_parent:
            continue
        parent_counts[parent_id] = count + 1
        limited.append(document)
    return limited


def select_unique_parent_children(
    documents: Sequence[Document],
    k: int,
) -> list[Document]:
    """从 child 排序结果中为每个 parent 选择最高分 child。"""
    selected: list[Document] = []
    parent_ids: set[str] = set()
    for document in documents:
        parent_id = str(document.metadata.get("parent_id") or "")
        if not parent_id or parent_id in parent_ids:
            continue
        parent_ids.add(parent_id)
        selected.append(document)
        if len(selected) >= k:
            break
    return selected


def expand_parent_contexts(
    *,
    documents: Sequence[Document],
    user_id: int,
    context_budget_characters: int = 12_000,
) -> list[Document]:
    """直接使用 Milvus entity 的 parent 正文扩展 LLM context。"""
    if context_budget_characters < 1:
        raise ValueError("context_budget_characters 必须大于 0")
    expanded: list[Document] = []
    remaining = context_budget_characters
    errors: list[str] = []
    for document in documents:
        child_metadata = dict(document.metadata)
        parent_id = str(child_metadata.get("parent_id") or "")
        parent_content = str(child_metadata.get("parent_content") or "")
        if not parent_id or not parent_content:
            errors.append(f"parent context 缺失：{parent_id}")
            continue

        if remaining <= 0:
            break
        context_content = parent_content[:remaining]
        remaining -= len(context_content)
        metadata = dict(child_metadata)
        metadata.pop("parent_content", None)
        metadata.update({
            "user_id": user_id,
            "parent_id": parent_id,
            "child_id": metadata.get("child_id") or metadata.get("chunk_id"),
            "child_content": document.page_content,
            "parent_context_expanded": True,
            "parent_context_truncated": len(context_content) < len(parent_content),
        })
        expanded.append(Document(
            page_content=context_content,
            metadata=metadata,
        ))

    update_retrieval_diagnostics(
        parent_count=len(expanded),
        parent_context_degraded=bool(errors),
        parent_context_errors=errors,
        parent_context_budget_characters=context_budget_characters,
        parent_context_used_characters=(
            context_budget_characters - remaining
        ),
    )
    return expanded


def get_milvus_hybrid_documents(
    *,
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None,
    k: int,
    dense_k: int,
    sparse_k: int,
    rrf_k: int,
    rerank: bool,
    reranker_model: str,
) -> list[Document]:
    """执行 Milvus v3 dense/sparse 检索、child rerank 与 parent 扩展。"""
    reset_retrieval_diagnostics()
    update_retrieval_diagnostics(retrieval_mode="milvus_dense_sparse")
    total_started_at = perf_counter()

    query_embedding: list[float] | None = None
    dense_started_at = perf_counter()
    try:
        query_embedding = get_query_embedding(query, user_id)
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_dense_embedding_failed",
            exc,
            default_source="embedding",
            user_id=user_id,
            stage="dense_embedding",
            message="dense query vector 生成失败，尝试 sparse-only 降级",
        )
        add_dense_diagnostic_error("dense query vector 生成失败")
    record_retrieval_timing("dense_embedding", dense_started_at)

    query_sparse_embedding: dict[int, float] | None = None
    sparse_started_at = perf_counter()
    try:
        query_sparse_embedding = get_query_sparse_embedding(query, user_id)
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_sparse_embedding_failed",
            exc,
            default_source="sparse_encoder",
            user_id=user_id,
            stage="sparse_embedding",
            message="sparse query vector 生成失败，尝试 dense-only 降级",
        )
        add_sparse_diagnostic_error("sparse query vector 生成失败")
    record_retrieval_timing("sparse_embedding", sparse_started_at)

    if query_embedding is None and query_sparse_embedding is None:
        add_hybrid_diagnostic_error("dense/sparse query vector 均生成失败")
        record_retrieval_timing("retrieval_total", total_started_at)
        return []

    vector_store = get_vector_store(user_id=user_id)
    hybrid_started_at = perf_counter()
    try:
        response = vector_store.hybrid_search_vectors(
            query_embedding=query_embedding,
            query_sparse_embedding=query_sparse_embedding,
            user_id=user_id,
            file_ids=list(file_ids) if file_ids else None,
            dense_k=dense_k,
            sparse_k=sparse_k,
            k=rrf_k,
            rrf_rank_constant=60,
        )
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_milvus_hybrid_failed",
            exc,
            default_source="milvus",
            user_id=user_id,
            stage="hybrid",
            message="Milvus hybrid search 失败",
        )
        add_hybrid_diagnostic_error("Milvus hybrid search 失败")
        response = None
        if query_embedding is not None and query_sparse_embedding is not None:
            try:
                response = vector_store.hybrid_search_vectors(
                    query_embedding=query_embedding,
                    query_sparse_embedding=None,
                    user_id=user_id,
                    file_ids=list(file_ids) if file_ids else None,
                    dense_k=dense_k,
                    sparse_k=sparse_k,
                    k=rrf_k,
                    rrf_rank_constant=60,
                )
            except Exception as dense_exc:
                log_exception_event(
                    logger,
                    "retrieval_milvus_dense_fallback_failed",
                    dense_exc,
                    default_source="milvus",
                    user_id=user_id,
                    stage="dense_fallback",
                    message="Milvus dense-only fallback 失败，尝试 sparse-only",
                )
                add_dense_diagnostic_error("Milvus dense-only search 失败")
                try:
                    response = vector_store.hybrid_search_vectors(
                        query_embedding=None,
                        query_sparse_embedding=query_sparse_embedding,
                        user_id=user_id,
                        file_ids=list(file_ids) if file_ids else None,
                        dense_k=dense_k,
                        sparse_k=sparse_k,
                        k=rrf_k,
                        rrf_rank_constant=60,
                    )
                except Exception as sparse_exc:
                    log_exception_event(
                        logger,
                        "retrieval_milvus_sparse_fallback_failed",
                        sparse_exc,
                        default_source="milvus",
                        user_id=user_id,
                        stage="sparse_fallback",
                        message="Milvus sparse-only fallback 失败",
                    )
                    add_sparse_diagnostic_error(
                        "Milvus sparse-only search 失败",
                    )
            else:
                add_sparse_diagnostic_error(
                    "Milvus hybrid search 失败，已降级为 dense-only",
                )
        if response is None:
            record_retrieval_timing("hybrid", hybrid_started_at)
            record_retrieval_timing("retrieval_total", total_started_at)
            return []
    record_retrieval_timing("hybrid", hybrid_started_at)

    documents = [result.document for result in response.results]
    for issue in response.issues:
        add_hybrid_diagnostic_error(issue.message)
    result_sources = {
        source
        for document in documents
        for source in document.metadata.get("retrieval_sources", [])
    }
    both_routes = result_sources == {"dense", "sparse"}
    update_retrieval_diagnostics(
        dense_count=None if both_routes else (
            len(documents) if "dense" in result_sources else 0
        ),
        sparse_count=None if both_routes else (
            len(documents) if "sparse" in result_sources else 0
        ),
        route_counts_available=not both_routes,
        hybrid_count=len(documents),
        fused_count=len(documents),
        retrieval_sources=sorted(result_sources),
    )
    candidates = limit_child_candidates_by_parent(documents)
    update_retrieval_diagnostics(
        parent_limited_candidate_count=len(candidates),
        max_children_per_parent=MAX_CHILD_CANDIDATES_PER_PARENT,
    )

    ordered_children = candidates
    if rerank and candidates:
        rerank_started_at = perf_counter()
        try:
            ordered_children = get_reranker(
                reranker_model,
                user_id=user_id,
            ).rerank(
                query=query,
                documents=candidates,
                top_k=len(candidates),
                max_length=DEFAULT_RERANKER_MAX_LENGTH,
            )
        except Exception as exc:
            log_exception_event(
                logger,
                "retrieval_rerank_failed",
                exc,
                default_source="rerank",
                user_id=user_id,
                stage="rerank",
                fused_count=len(candidates),
                message="rerank 精排失败，降级为 Milvus RRF 顺序",
            )
            update_retrieval_diagnostics(
                reranked_count=0,
                rerank_degraded=True,
                rerank_errors=["rerank 精排失败"],
            )
        else:
            update_retrieval_diagnostics(reranked_count=len(ordered_children))
        record_retrieval_timing("rerank", rerank_started_at)
    elif rerank:
        update_retrieval_diagnostics(
            reranked_count=0,
            rerank_skipped=True,
            rerank_skip_reason="no_hybrid_candidates",
        )

    selected_children = select_unique_parent_children(ordered_children, k)
    parent_started_at = perf_counter()
    try:
        expanded_documents = expand_parent_contexts(
            documents=selected_children,
            user_id=user_id,
        )
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_parent_context_failed",
            exc,
            default_source="milvus",
            user_id=user_id,
            stage="parent_context",
            message="Milvus parent context 扩展失败，拒绝返回缺失正文的 child",
        )
        update_retrieval_diagnostics(
            parent_context_degraded=True,
            parent_context_errors=["parent context 扩展失败"],
        )
        expanded_documents = []
    record_retrieval_timing("parent_context", parent_started_at)
    record_retrieval_timing("retrieval_total", total_started_at)
    return expanded_documents


def get_hybrid_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
    vector_k: int = 20,
    sparse_k: int = 20,
    rrf_k: int = 10,
    rerank: bool = True,
    reranker_model: str = DEFAULT_RERANKER_MODEL,
) -> list[Document]:
    """执行 Milvus dense/sparse RRF、child rerank 和 parent context 扩展。"""
    return get_milvus_hybrid_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=k,
        dense_k=vector_k,
        sparse_k=sparse_k,
        rrf_k=rrf_k,
        rerank=rerank,
        reranker_model=reranker_model,
    )
