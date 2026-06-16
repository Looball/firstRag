from collections.abc import Sequence
from uuid import UUID

from langchain_core.documents import Document

from app.services.retrieval.fulltext_retriever import get_fulltext_documents
from app.services.retrieval.reranker import get_reranker
from app.services.retrieval.rrf import reciprocal_rank_fusion
from app.services.vectors.vector_index_service import get_vector_store


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


def get_vector_documents(
    query: str,
    user_id: int,
    file_ids: Sequence[UUID | str] | None = None,
    k: int = 5,
) -> list[Document]:
    """从 Chroma 中按用户和文件范围做向量检索。"""
    vectordb = get_vector_store()
    documents = vectordb.similarity_search(
        query=query,
        k=k,
        filter=build_chroma_filter(
            user_id=user_id,
            file_ids=file_ids,
        ),
    )

    for document in documents:
        document.metadata["retrieval_source"] = "vector"

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
    reranker_model: str = "BAAI/bge-reranker-base",
) -> list[Document]:
    """执行混合召回、RRF 融合，并可选使用 Cross-Encoder 精排序。"""
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
