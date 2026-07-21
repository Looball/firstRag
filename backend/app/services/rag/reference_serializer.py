from typing import Any

from langchain_core.documents import Document

from app.services.rag.retrieval_decision import normalize_retrieval_settings

REFERENCE_RERANK_SCORE_THRESHOLD = 0.0

def is_reference_document_relevant(
    doc: Document,
    rerank_score_threshold: float = REFERENCE_RERANK_SCORE_THRESHOLD,
) -> bool:
    """判断检索片段是否足够可信，可以进入上下文和前端引用。

    BGE Cross-Encoder reranker 输出 raw logits，分数越大越相关。
    当前混合检索默认启用 reranker，因此低于 0 的片段通常是弱相关或
    误召回片段，不应在用户只问“你好”这类问题时展示成来源。
    如果历史数据或降级路径没有 rerank_score，则保持兼容，暂不拦截。
    """
    score = doc.metadata.get("rerank_score")
    if score is None:
        return True

    try:
        return float(score) >= rerank_score_threshold
    except (TypeError, ValueError):
        return True


def filter_relevant_reference_documents(
    docs: list[Document],
    rerank_score_threshold: float = REFERENCE_RERANK_SCORE_THRESHOLD,
) -> list[Document]:
    """过滤掉低相关检索片段，避免误展示 Sources。"""
    return [
        doc
        for doc in docs
        if isinstance(doc, Document)
        and is_reference_document_relevant(doc, rerank_score_threshold)
    ]


def get_reference_threshold_from_docs(docs: list[Document]) -> float:
    """从文档 metadata 读取本轮引用展示阈值，缺失时使用默认值。"""
    for doc in docs:
        if not isinstance(doc, Document):
            continue
        threshold = doc.metadata.get("rerank_score_threshold")
        try:
            return float(threshold)
        except (TypeError, ValueError):
            continue

    return REFERENCE_RERANK_SCORE_THRESHOLD

def get_res_doc(inputs: dict[str, Any]) -> str:
    """将检索到的文档列表格式化为提示词上下文。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    docs = filter_relevant_reference_documents(
        inputs.get("context", []),
        rerank_score_threshold=float(settings["rerank_score_threshold"]),
    )
    context_parts = []

    for index, doc in enumerate(docs, start=1):
        metadata = doc.metadata
        source = metadata.get("file_name") or metadata.get("source", "")
        chunk_index = metadata.get("chunk_index", "")
        context_parts.append(
            f"[片段 {index}]"
            f" 来源：{source}"
            f" chunk：{chunk_index}\n"
            f"{doc.page_content}"
        )

    return "\n\n".join(context_parts)


def serialize_reference_documents(
    docs: list[Document],
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """将检索到的文档片段转换为前端可展示的引用结构。

    返回的每个引用对象将来源信息和排序分数扁平放在顶层，
    方便前端直接读取。file_name 使用数据库中用户上传的原始文件名，
    而非磁盘存储的统称名。
    """
    from app.repositories.knowledge_file_repository import (
        get_file_original_names,
    )

    # 批量查询 file_id → 原始文件名 映射
    file_ids = list({
        doc.metadata.get("file_id")
        for doc in docs
        if isinstance(doc, Document) and doc.metadata.get("file_id")
    })
    original_names = (
        get_file_original_names(user_id, file_ids)
        if user_id is not None and file_ids
        else {}
    )

    references = []
    relevant_docs = filter_relevant_reference_documents(
        docs,
        rerank_score_threshold=get_reference_threshold_from_docs(docs),
    )
    for index, doc in enumerate(relevant_docs, start=1):
        metadata = doc.metadata
        doc_file_id = metadata.get("file_id", "")

        references.append({
            "index": index,
            "content": doc.page_content,
            "source": metadata.get("source"),
            "file_id": doc_file_id,
            "file_name": original_names.get(doc_file_id)
                          or metadata.get("file_name"),
            "file_type": metadata.get("file_type"),
            "chunk_index": metadata.get("chunk_index"),
            "index_version": metadata.get("index_version"),
            "page_index": metadata.get("page_index"),
            "page_number": metadata.get("page_number"),
            "page_count": metadata.get("page_count"),
            "paragraph_start": metadata.get("paragraph_start"),
            "paragraph_end": metadata.get("paragraph_end"),
            "pdf_parse_method": metadata.get("pdf_parse_method"),
            "ocr_engine": metadata.get("ocr_engine"),
            "ocr_languages": metadata.get("ocr_languages"),
            "ocr_dpi": metadata.get("ocr_dpi"),
            "retrieval_sources": metadata.get("retrieval_sources"),
            "vector_score": metadata.get("vector_score"),
            "fulltext_score": metadata.get("fulltext_score"),
            "rrf_score": metadata.get("rrf_score"),
            "rerank_score": metadata.get("rerank_score"),
        })

    return references
