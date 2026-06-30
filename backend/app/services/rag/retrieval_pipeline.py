from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.documents import Document

from app.repositories.knowledge_base_repository import get_knowledge_base_files
from app.repositories.retrieval_settings_repository import (
    get_knowledge_base_retrieval_settings,
)
from app.services.knowledge_profile_cache import (
    get_cached_knowledge_base_context,
)
from app.services.rag.diagnostics import (
    RETRIEVAL_SETTINGS_DIAGNOSTICS_KEY,
    elapsed_ms,
    extract_retrieval_settings_diagnostics,
    merge_knowledge_profile_cache_diagnostics,
    merge_retrieval_settings_diagnostics,
    _retrieval_settings_diagnostics,
)
from app.services.rag.retrieval_decision import (
    normalize_retrieval_decision,
    normalize_retrieval_settings,
)
from app.services.rag.types import (
    ChainInput,
    MAX_KNOWLEDGE_PROFILE_FILES,
    RetrievedDocs,
)
from app.services.retrieval.hybrid_retriever import (
    get_hybrid_documents,
    get_retrieval_diagnostics,
)
from app.services.retrieval_settings_cache import (
    get_cached_knowledge_base_retrieval_settings,
    get_retrieval_settings_cache_diagnostics,
)

def load_retrieval_settings(inputs: ChainInput) -> dict:
    """读取当前知识库的检索设置，未配置时使用默认值。"""
    total_started_at = perf_counter()
    query_started_at = perf_counter()
    settings = get_cached_knowledge_base_retrieval_settings(
        knowledge_base_id=inputs["knowledge_base_id"],
        user_id=inputs["user_id"],
        load_settings=lambda: get_knowledge_base_retrieval_settings(
            knowledge_base_id=inputs["knowledge_base_id"],
            user_id=inputs["user_id"],
        ),
    )
    query_ms = elapsed_ms(query_started_at)

    normalize_started_at = perf_counter()
    normalized_settings = normalize_retrieval_settings(settings)
    normalize_ms = elapsed_ms(normalize_started_at)
    cache_diagnostics = get_retrieval_settings_cache_diagnostics()
    settings_diagnostics = {
        "retrieval_settings_query_ms": query_ms,
        "retrieval_settings_normalize_ms": normalize_ms,
        "retrieval_settings_load_total_ms": elapsed_ms(total_started_at),
        "retrieval_settings_source": (
            cache_diagnostics.get("retrieval_settings_source")
            if isinstance(cache_diagnostics, dict)
            else ("database" if settings else "default")
        ),
        "cache": cache_diagnostics,
    }
    _retrieval_settings_diagnostics.set(settings_diagnostics)
    normalized_settings[RETRIEVAL_SETTINGS_DIAGNOSTICS_KEY] = dict(
        settings_diagnostics,
    )
    return normalized_settings

def build_knowledge_base_profile(inputs: ChainInput) -> str:
    """根据当前知识库文件列表生成轻量知识库画像。

    先不引入新的摘要表，使用文件名、类型和索引状态帮助 Router 判断
    用户问题是否可能需要知识库。后续可以将这里替换为文件摘要/标签表。
    """
    context = get_cached_knowledge_base_context(
        user_id=inputs["user_id"],
        knowledge_base_id=inputs["knowledge_base_id"],
        load_rows=lambda: get_knowledge_base_files(
            knowledge_base_id=inputs["knowledge_base_id"],
            user_id=inputs["user_id"],
        ),
        max_profile_files=MAX_KNOWLEDGE_PROFILE_FILES,
    )
    return context.profile

def get_knowledge_base_file_ids(
    user_id: int,
    knowledge_base_id: UUID,
) -> list[str]:
    """查询知识库中已完成向量化的文件 ID 列表。

    只返回 status='indexed' 的文件，避免 ChromaDB 查找未向量化
    文件 ID 时触发 HNSW 内部错误。
    """
    context = get_cached_knowledge_base_context(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        load_rows=lambda: get_knowledge_base_files(
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
        ),
        max_profile_files=MAX_KNOWLEDGE_PROFILE_FILES,
    )
    return context.file_ids


def retrieve_documents(inputs: ChainInput) -> RetrievedDocs:
    """根据当前知识库范围执行混合检索。"""
    user_id = inputs["user_id"]
    knowledge_base_id = inputs["knowledge_base_id"]
    raw_settings = inputs.get("retrieval_settings")
    settings = normalize_retrieval_settings(raw_settings)
    decision = normalize_retrieval_decision(
        inputs.get("retrieval_decision"),
    )
    if not decision["need_retrieval"]:
        return []

    query = decision["rewritten_query"] or inputs["standalone_question"]

    file_ids = get_knowledge_base_file_ids(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    if not file_ids:
        return []

    docs = get_hybrid_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=int(settings["top_k"]),
        vector_k=int(settings["vector_top_k"]),
        fulltext_k=int(settings["fulltext_top_k"]),
        rrf_k=int(settings["rrf_k"]),
        rerank=bool(settings["enable_rerank"]),
    )
    diagnostics = get_retrieval_diagnostics()
    if diagnostics is not None:
        diagnostics["settings"] = settings
        diagnostics = merge_retrieval_settings_diagnostics(
            diagnostics,
            extract_retrieval_settings_diagnostics(raw_settings),
        )
        diagnostics = merge_knowledge_profile_cache_diagnostics(diagnostics)
        # LCEL 流式执行过程中 ContextVar 可能跨 Runnable 丢失。
        # 将诊断挂到文档 metadata，确保后续 SSE 和落库能稳定读取。
        for doc in docs:
            doc.metadata["retrieval_diagnostics"] = diagnostics
            doc.metadata["rerank_score_threshold"] = settings[
                "rerank_score_threshold"
            ]
    return docs


def extract_retrieval_diagnostics_from_docs(
    docs: list[Document],
) -> dict[str, Any] | None:
    """从检索文档 metadata 中提取混合检索诊断信息。"""
    for doc in docs:
        diagnostics = doc.metadata.get("retrieval_diagnostics")
        if isinstance(diagnostics, dict):
            return diagnostics
    return None
