"""基于 provider-neutral boundary 的向量粗召回。

向量检索使用 bi-encoder 思路：文档 chunk 在入库时提前编码成向量，
用户查询时只编码 query，再通过向量相似度快速召回候选 chunk。

这种方式适合做第一阶段粗召回，因为它可以在较大的向量库中快速查找
语义相近的片段。但 bi-encoder 的 query 和 document 是分开编码的，
交互不充分，所以召回结果不应该直接作为最终排序。当前项目会将向量
召回结果与全文检索结果通过 RRF 融合，再交给 Cross-Encoder 精排序。
"""

from typing import Any

from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda

from app.services.vectors.embedding_model import create_embedding_model
from app.services.vectors.vector_store_factory import get_vector_store


def get_retriever(
    user_id: int | None = None,
    search_type: str = "similarity",
    search_kwargs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Runnable[str, list[Document]]:
    """创建只依赖统一 vector store 契约的 Runnable 检索器。"""
    if user_id is None:
        raise ValueError("创建向量检索器需要 user_id")
    if search_type != "similarity":
        raise ValueError("provider-neutral 检索器仅支持 similarity")
    if kwargs:
        raise ValueError("provider-neutral 检索器不接受额外 provider 参数")

    vector_store = get_vector_store(user_id=user_id)
    embedding_model = create_embedding_model(user_id)
    resolved_search_kwargs = search_kwargs or {"k": 5}
    k = int(resolved_search_kwargs.get("k", 5))

    def retrieve(query: str) -> list[Document]:
        """生成 query embedding 并返回按 distance 排序的文档。"""
        response = vector_store.search_vectors(
            query_embedding=embedding_model.embed_query(query),
            user_id=user_id,
            file_ids=None,
            k=k,
        )
        return [result.document for result in response.results]

    return RunnableLambda(retrieve)


def get_res_doc(inputs: dict[str, Any]) -> str:
    """提取检索器返回文档的正文。"""
    docs = inputs.get("context", [])
    return "\n\n".join(
        doc.page_content
        for doc in docs
        if isinstance(doc, Document)
    )
