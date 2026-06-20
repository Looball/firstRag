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
from uuid import UUID

from langchain_core.documents import Document

from app.services.retrieval.fulltext_retriever import get_fulltext_documents
from app.services.retrieval.reranker import DEFAULT_RERANKER_MODEL, get_reranker
from app.services.retrieval.rrf import reciprocal_rank_fusion
from app.services.vectors.embedding_model import ZhipuAIEmbeddings
from app.services.vectors.vector_index_service import get_vector_store

logger = logging.getLogger(__name__)


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
    vectordb = get_vector_store()
    try:
        # 外部预计算 embedding，绕过 ChromaDB query_texts 路径
        embedding_model = ZhipuAIEmbeddings()
        query_embedding = embedding_model.embed_query(query)

        if file_ids:
            scored_candidates = []
            for file_id in {str(file_id) for file_id in file_ids}:
                scored_candidates.extend(
                    vectordb.similarity_search_by_vector_with_relevance_scores(
                        embedding=query_embedding,
                        k=k,
                        filter=build_file_chroma_filter(user_id, file_id),
                    )
                )
            # Chroma 返回的是距离，数值越小语义越相近。
            scored_candidates.sort(key=lambda item: item[1])
            candidates = scored_candidates[:k]
        else:
            candidates = vectordb.similarity_search_by_vector_with_relevance_scores(
                embedding=query_embedding,
                k=k,
                filter={"user_id": str(user_id)},
            )
    except Exception:
        logger.exception("Chroma 向量检索失败，降级为空结果")
        return []

    documents = []
    for document, score in candidates:
        document.metadata["retrieval_source"] = "vector"
        document.metadata["vector_score"] = float(score)
        documents.append(document)

    return documents


def get_hybrid_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
    vector_k: int = 20,
    fulltext_k: int = 20,
    rrf_k: int = 20,
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
    vector_documents = get_vector_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=vector_k,
    )
    fulltext_documents = get_fulltext_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=fulltext_k,
    )

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

    if not rerank:
        return fused_documents

    return get_reranker(reranker_model).rerank(
        query=query,
        documents=fused_documents,
        top_k=k,
    )
