"""混合检索流水线。

本模块采用三阶段检索策略：

1. 粗召回：使用 Chroma 向量检索和 PostgreSQL 全文检索分别召回候选。
   向量检索擅长语义相似，全文检索擅长精确关键词、专有名词和编号。
   两者都是低成本召回器，目标是尽量提高候选覆盖率，而不是最终排序。

2. RRF 融合：将不同召回器的有序结果列表做去重和排名融合。
   RRF 只依赖各召回器内部排名，不直接比较向量距离和全文检索分数，
   因此适合融合分数尺度不同的检索结果。

3. Cross-Encoder 精排序：对融合后的少量候选逐条计算 query-document
   相关性分数。Cross-Encoder 比 bi-encoder 更准确但更慢，所以只用于
   最终候选池，而不是直接对全库或每一路大量结果排序。
"""

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from threading import RLock
from time import monotonic
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.core.observability import log_exception_event
from app.services.retrieval.fulltext_retriever import get_fulltext_documents
from app.services.retrieval.reranker import (
    DEFAULT_RERANKER_MAX_LENGTH,
    DEFAULT_RERANKER_MODEL,
    get_reranker,
)
from app.services.retrieval.rrf import reciprocal_rank_fusion
from app.services.vectors.embedding_model import (
    create_embedding_model,
    get_embedding_cache_identity,
)
from app.services.vectors.vector_index_service import get_vector_store

logger = logging.getLogger(__name__)

QUERY_EMBEDDING_CACHE_TTL_SECONDS = 300.0
MAX_VECTOR_FILTER_FALLBACK_CANDIDATES = 100

_QUERY_EMBEDDING_CACHE: dict[
    tuple[str, str, str, str, str],
    tuple[float, list[float]],
] = {}
_QUERY_EMBEDDING_CACHE_LOCK = RLock()

_RETRIEVAL_DIAGNOSTICS: ContextVar[dict[str, Any] | None] = ContextVar(
    "retrieval_diagnostics",
    default=None,
)


def reset_retrieval_diagnostics() -> None:
    """初始化当前请求的检索诊断信息。"""
    _RETRIEVAL_DIAGNOSTICS.set({
        "vector_degraded": False,
        "vector_errors": [],
        "fulltext_degraded": False,
        "fulltext_errors": [],
        "query_embedding_cache_hit": False,
        "query_embedding_cache_key": "",
        "query_embedding_cache_ttl_seconds": QUERY_EMBEDDING_CACHE_TTL_SECONDS,
        "vector_count": 0,
        "fulltext_count": 0,
        "fused_count": 0,
        "reranked_count": 0,
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


def add_vector_diagnostic_error(message: str) -> None:
    """记录一次向量检索降级原因。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return

    diagnostics["vector_degraded"] = True
    errors = diagnostics.setdefault("vector_errors", [])
    errors.append(message)


def add_fulltext_diagnostic_error(message: str) -> None:
    """记录一次全文检索降级原因。"""
    diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if diagnostics is None:
        return

    diagnostics["fulltext_degraded"] = True
    errors = diagnostics.setdefault("fulltext_errors", [])
    errors.append(message)


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


def clear_query_embedding_cache() -> None:
    """清空 query embedding 进程内缓存，主要用于测试。"""
    with _QUERY_EMBEDDING_CACHE_LOCK:
        _QUERY_EMBEDDING_CACHE.clear()


def get_query_embedding(query: str, user_id: int) -> list[float]:
    """读取或生成 query embedding，成功结果写入短 TTL 进程内缓存。"""
    cache_key = build_query_embedding_cache_key(query, user_id)
    now = monotonic()

    with _QUERY_EMBEDDING_CACHE_LOCK:
        cached = _QUERY_EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            expires_at, embedding = cached
            if expires_at > now:
                update_retrieval_diagnostics(
                    query_embedding_cache_hit=True,
                    query_embedding_cache_key=":".join(cache_key),
                )
                return list(embedding)
            _QUERY_EMBEDDING_CACHE.pop(cache_key, None)

    update_retrieval_diagnostics(
        query_embedding_cache_hit=False,
        query_embedding_cache_key=":".join(cache_key),
    )
    embedding_model = create_embedding_model(user_id)
    embedding = list(embedding_model.embed_query(query))

    with _QUERY_EMBEDDING_CACHE_LOCK:
        _QUERY_EMBEDDING_CACHE[cache_key] = (
            now + QUERY_EMBEDDING_CACHE_TTL_SECONDS,
            list(embedding),
        )

    return embedding


def build_chroma_filter(
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
) -> dict:
    """构造 Chroma metadata 过滤条件。"""
    user_filter = {"user_id": str(user_id)}
    if not file_ids:
        return user_filter

    return {
        "$and": [
            user_filter,
            {
                "file_id": {
                    "$in": [
                        str(file_id)
                        for file_id in file_ids
                    ]
                }
            },
        ]
    }


def build_file_chroma_filter(user_id: int, file_id: UUID | str) -> dict:
    """构造单文件的 Chroma metadata 过滤条件。

    不使用 `$in` 批量过滤，规避当前 Chroma Rust backend 的复杂过滤问题；
    单文件等值过滤仍由 Chroma 在向量召回前执行。
    """
    return {
        "$and": [
            {"user_id": str(user_id)},
            {"file_id": str(file_id)},
        ]
    }


def retry_file_vector_search_without_file_filter(
    *,
    vectordb: Any,
    query_embedding: list[float],
    user_id: int,
    file_id: UUID | str,
    k: int,
) -> list[tuple[Document, float]]:
    """单文件过滤失败时，退回用户级检索并在 Python 侧过滤文件。

    Chroma HNSW 删除/重建后偶发 `Error finding id`，常见于带 metadata
    文件过滤的查询。用户级过滤更宽，命中后再按 file_id 过滤，避免一次
    Chroma 内部索引残留错误让该文件完全失去 vector 召回机会。
    """
    fallback_k = min(max(k * 5, k), MAX_VECTOR_FILTER_FALLBACK_CANDIDATES)
    candidates = vectordb.similarity_search_by_vector_with_relevance_scores(
        embedding=query_embedding,
        k=fallback_k,
        filter={"user_id": str(user_id)},
    )
    normalized_file_id = str(file_id)
    return [
        (document, score)
        for document, score in candidates
        if str(document.metadata.get("file_id") or "") == normalized_file_id
    ][:k]


def get_vector_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
) -> list[Document]:
    """从 Chroma 中按用户和文件范围做向量检索。

    ChromaDB 1.5.x Rust backend 在内部调用 embedding 函数（query_texts
    路径）时会触发 SSL 超时或 HNSW Error finding id。本函数改为在外部
    预计算 query embedding，通过 query_embeddings 路径查询，完全绕过
    ChromaDB 内部 embedding 调用链。

    指定知识库文件范围时，逐个文件在 Chroma 侧进行等值过滤，再按向量
    距离合并排序。这样不会因其它知识库的高分文档占满固定候选池而漏召回。
    """
    embedding_started_at = perf_counter()
    try:
        # 外部预计算 embedding，绕过 ChromaDB query_texts 路径
        query_embedding = get_query_embedding(query, user_id)
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_embedding_failed",
            exc,
            default_source="embedding",
            user_id=user_id,
            file_count=len(file_ids or []),
            stage="embedding",
            message="查询向量生成失败，降级为空向量结果",
        )
        add_vector_diagnostic_error("查询向量生成失败")
        record_retrieval_timing("embedding", embedding_started_at)
        return []
    record_retrieval_timing("embedding", embedding_started_at)

    vectordb = get_vector_store(user_id=user_id)
    vector_started_at = perf_counter()
    try:
        if not file_ids:
            candidates = vectordb.similarity_search_by_vector_with_relevance_scores(
                embedding=query_embedding,
                k=k,
                filter={"user_id": str(user_id)},
            )
        else:
            scored_candidates = []
            for file_id in sorted({str(file_id) for file_id in file_ids}):
                try:
                    scored_candidates.extend(
                        vectordb.similarity_search_by_vector_with_relevance_scores(
                            embedding=query_embedding,
                            k=k,
                            filter=build_file_chroma_filter(user_id, file_id),
                        )
                    )
                except Exception as exc:
                    try:
                        fallback_candidates = (
                            retry_file_vector_search_without_file_filter(
                                vectordb=vectordb,
                                query_embedding=query_embedding,
                                user_id=user_id,
                                file_id=file_id,
                                k=k,
                            )
                        )
                    except Exception:
                        fallback_candidates = []

                    if fallback_candidates:
                        scored_candidates.extend(fallback_candidates)
                        continue

                    # Chroma 删除/重建向量后偶发 HNSW 残留错误。
                    # 单文件失败不应拖垮整个知识库检索，后续仍可依赖其它文件
                    # 和 PostgreSQL 全文检索兜底。
                    log_exception_event(
                        logger,
                        "retrieval_vector_file_failed",
                        exc,
                        default_source="vector_store",
                        user_id=user_id,
                        file_id=file_id,
                        stage="vector",
                        message="Chroma 单文件向量检索失败，跳过该文件",
                    )
                    add_vector_diagnostic_error(
                        f"Chroma 单文件向量检索失败：{file_id}",
                    )
                    continue

            # Chroma 返回的是距离，数值越小语义越相近。
            scored_candidates.sort(key=lambda item: item[1])
            candidates = scored_candidates[:k]
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_vector_failed",
            exc,
            default_source="vector_store",
            user_id=user_id,
            file_count=len(file_ids or []),
            stage="vector",
            message="Chroma 向量检索失败，降级为空向量结果",
        )
        add_vector_diagnostic_error("Chroma 向量检索失败")
        record_retrieval_timing("vector", vector_started_at)
        return []
    record_retrieval_timing("vector", vector_started_at)

    documents = []
    for document, score in candidates:
        document.metadata["retrieval_source"] = "vector"
        document.metadata["vector_score"] = float(score)
        documents.append(document)

    update_retrieval_diagnostics(vector_count=len(documents))
    return documents


def get_vector_documents_with_diagnostics(
    *,
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None,
    k: int,
) -> tuple[list[Document], dict[str, Any]]:
    """在线程内执行向量召回，并返回该线程产生的诊断信息。"""
    reset_retrieval_diagnostics()
    try:
        documents = get_vector_documents(
            query=query,
            user_id=user_id,
            file_ids=file_ids,
            k=k,
        )
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_vector_coarse_failed",
            exc,
            default_source="vector_store",
            user_id=user_id,
            file_count=len(file_ids or []),
            stage="vector_coarse",
            message="向量粗召回失败，降级为空向量结果",
        )
        add_vector_diagnostic_error("向量粗召回失败")
        documents = []

    diagnostics = get_retrieval_diagnostics() or {}
    return documents, diagnostics


def get_fulltext_documents_with_timing(
    *,
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None,
    k: int,
) -> tuple[list[Document], float, str | None]:
    """执行全文召回并返回耗时；失败时返回空结果和错误信息。"""
    started_at = perf_counter()
    try:
        documents = get_fulltext_documents(
            query=query,
            user_id=user_id,
            file_ids=file_ids,
            k=k,
        )
        error_message = None
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_fulltext_failed",
            exc,
            default_source="postgres",
            user_id=user_id,
            file_count=len(file_ids or []),
            stage="fulltext",
            message="全文粗召回失败，降级为空全文结果",
        )
        documents = []
        error_message = "全文粗召回失败"

    elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
    return documents, elapsed_ms, error_message


def merge_vector_diagnostics(diagnostics: dict[str, Any]) -> None:
    """将线程内向量召回诊断合并回当前请求诊断。"""
    timing = diagnostics.get("timing")
    if isinstance(timing, dict):
        current = _RETRIEVAL_DIAGNOSTICS.get()
        if current is not None:
            current_timing = current.setdefault("timing", {})
            for key in ("embedding_ms", "vector_ms"):
                if key in timing:
                    current_timing[key] = timing[key]

    update_retrieval_diagnostics(
        vector_degraded=bool(diagnostics.get("vector_degraded")),
        vector_errors=list(diagnostics.get("vector_errors") or []),
        query_embedding_cache_hit=bool(
            diagnostics.get("query_embedding_cache_hit"),
        ),
        query_embedding_cache_key=str(
            diagnostics.get("query_embedding_cache_key") or "",
        ),
    )


def get_hybrid_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
    vector_k: int = 20,
    fulltext_k: int = 20,
    rrf_k: int = 10,
    vector_weight: float = 1.0,
    fulltext_weight: float = 1.0,
    rerank: bool = True,
    reranker_model: str = DEFAULT_RERANKER_MODEL,
) -> list[Document]:
    """执行混合召回、RRF 融合，并可选使用 Cross-Encoder 精排序。

    检索顺序是先多路粗召回，再 RRF 融合候选，最后统一精排序。
    这样可以让向量检索和全文检索召回到的片段都有机会进入
    Cross-Encoder，而不是只精排某一路召回结果。
    """
    reset_retrieval_diagnostics()
    total_started_at = perf_counter()

    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(
            get_vector_documents_with_diagnostics,
            query=query,
            user_id=user_id,
            file_ids=file_ids,
            k=vector_k,
        )
        fulltext_future = executor.submit(
            get_fulltext_documents_with_timing,
            query=query,
            user_id=user_id,
            file_ids=file_ids,
            k=fulltext_k,
        )

        vector_documents, vector_diagnostics = vector_future.result()
        fulltext_documents, fulltext_ms, fulltext_error = (
            fulltext_future.result()
        )

    merge_vector_diagnostics(vector_diagnostics)
    if fulltext_error:
        add_fulltext_diagnostic_error(fulltext_error)
    current_diagnostics = _RETRIEVAL_DIAGNOSTICS.get()
    if current_diagnostics is not None:
        current_diagnostics.setdefault("timing", {})["fulltext_ms"] = (
            fulltext_ms
        )
    update_retrieval_diagnostics(
        vector_count=len(vector_documents),
        fulltext_count=len(fulltext_documents),
    )

    rrf_started_at = perf_counter()
    fused_documents = reciprocal_rank_fusion(
        ranked_results=[
            vector_documents,
            fulltext_documents,
        ],
        k=rrf_k if rerank else k,
        weights=[
            vector_weight,
            fulltext_weight,
        ],
    )
    record_retrieval_timing("rrf", rrf_started_at)
    update_retrieval_diagnostics(
        fused_count=len(fused_documents),
        retrieval_sources=sorted({
            source
            for document in fused_documents
            for source in (
                document.metadata.get("retrieval_sources")
                or [document.metadata.get("retrieval_source")]
            )
            if source
        }),
    )

    if not rerank:
        record_retrieval_timing("retrieval_total", total_started_at)
        return fused_documents

    if len(fused_documents) <= k:
        update_retrieval_diagnostics(
            reranked_count=0,
            rerank_skipped=True,
            rerank_skip_reason="candidate_count_not_above_top_k",
        )
        record_retrieval_timing("retrieval_total", total_started_at)
        return fused_documents

    rerank_started_at = perf_counter()
    try:
        reranked_documents = get_reranker(
            reranker_model,
            user_id=user_id,
        ).rerank(
            query=query,
            documents=fused_documents,
            top_k=k,
            max_length=DEFAULT_RERANKER_MAX_LENGTH,
        )
    except Exception as exc:
        log_exception_event(
            logger,
            "retrieval_rerank_failed",
            exc,
            default_source="rerank",
            user_id=user_id,
            file_count=len(file_ids or []),
            stage="rerank",
            fused_count=len(fused_documents),
            message="rerank 精排失败，降级为 RRF 融合结果",
        )
        record_retrieval_timing("rerank", rerank_started_at)
        record_retrieval_timing("retrieval_total", total_started_at)
        update_retrieval_diagnostics(
            reranked_count=0,
            rerank_degraded=True,
            rerank_errors=["rerank 精排失败"],
        )
        return fused_documents[:k]

    record_retrieval_timing("rerank", rerank_started_at)
    record_retrieval_timing("retrieval_total", total_started_at)
    update_retrieval_diagnostics(reranked_count=len(reranked_documents))
    return reranked_documents
