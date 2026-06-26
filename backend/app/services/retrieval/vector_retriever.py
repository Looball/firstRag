"""Chroma 向量粗召回。

向量检索使用 bi-encoder 思路：文档 chunk 在入库时提前编码成向量，
用户查询时只编码 query，再通过向量相似度快速召回候选 chunk。

这种方式适合做第一阶段粗召回，因为它可以在较大的向量库中快速查找
语义相近的片段。但 bi-encoder 的 query 和 document 是分开编码的，
交互不充分，所以召回结果不应该直接作为最终排序。当前项目会将向量
召回结果与全文检索结果通过 RRF 融合，再交给 Cross-Encoder 精排序。
"""

from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores.base import VectorStoreRetriever

from app.core.config import CHROMA_COLLECTION_NAME, VECTOR_STORE_PATH
from app.services.vectors.vector_index_service import get_vector_store


def get_retriever(
    store_path: str = str(VECTOR_STORE_PATH),
    collection_name: str = CHROMA_COLLECTION_NAME,
    search_type: str = "similarity",
    search_kwargs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> VectorStoreRetriever:
    """从本地 Chroma 向量数据库创建检索器。"""
    vectordb = get_vector_store(
        persist_directory=store_path,
        collection_name=collection_name,
    )
    return vectordb.as_retriever(
        search_type=search_type,
        search_kwargs=search_kwargs or {"k": 5},
        **kwargs,
    )


def get_res_doc(inputs: dict[str, Any]) -> str:
    """提取检索器返回文档的正文。"""
    docs = inputs.get("context", [])
    return "\n\n".join(
        doc.page_content
        for doc in docs
        if isinstance(doc, Document)
    )
