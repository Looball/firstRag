"""Reciprocal Rank Fusion 排名融合。

RRF 用于融合多个召回器返回的有序结果列表，例如向量检索和全文检索。
它的核心思想是：一个文档在某个召回器中排名越靠前，贡献越高；
如果同一个文档被多个召回器同时召回，它的贡献会累加。

公式：

    score(d) = sum(weight_i / (rank_constant + rank_i(d)))

其中 rank_i(d) 是文档 d 在第 i 个召回器中的排名。rank_constant
用于平滑排名差距，默认 60 是常见经验值，可以避免某一路检索的第一名
过度压制其他结果。

RRF 不直接使用原始检索分数，因此适合融合分数尺度不同的结果：
向量相似度、全文检索 rank、BM25 分数或其他召回器的输出。
"""

from collections import defaultdict
from collections.abc import Sequence

from langchain_core.documents import Document


def get_document_key(document: Document) -> str:
    """获取可用于去重和融合排序的稳定文档键。"""
    metadata = document.metadata
    if metadata.get("chunk_id"):
        return str(metadata["chunk_id"])

    user_id = metadata.get("user_id", "")
    file_id = metadata.get("file_id", metadata.get("source", ""))
    chunk_index = metadata.get("chunk_index", "")
    if file_id != "" and chunk_index != "":
        return f"{user_id}:{file_id}:{chunk_index}"

    return document.page_content


def reciprocal_rank_fusion(
    ranked_results: Sequence[Sequence[Document]],
    k: int = 5,
    rank_constant: int = 60,
    weights: Sequence[float] | None = None,
) -> list[Document]:
    """使用 RRF 融合多个有序检索结果列表。

    本函数先根据 chunk_id 或 user_id:file_id:chunk_index 去重，
    再累加不同召回器给同一文档带来的倒数排名分数，最后按融合分数
    返回 top-k。
    """
    if weights is None:
        weights = [1.0] * len(ranked_results)
    if len(weights) != len(ranked_results):
        raise ValueError("weights 数量必须和 ranked_results 数量一致")

    documents_by_key: dict[str, Document] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    source_ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for result_index, documents in enumerate(ranked_results):
        weight = weights[result_index]
        for rank, document in enumerate(documents, start=1):
            key = get_document_key(document)
            scores[key] += weight / (rank_constant + rank)

            retrieval_source = str(
                document.metadata.get(
                    "retrieval_source",
                    f"retriever_{result_index}",
                )
            )
            source_ranks[key][retrieval_source] = rank

            if key not in documents_by_key:
                documents_by_key[key] = document
            else:
                documents_by_key[key].metadata.update(document.metadata)

    sorted_keys = sorted(
        scores,
        key=lambda item: scores[item],
        reverse=True,
    )

    fused_documents = []
    for fused_rank, key in enumerate(sorted_keys[:k], start=1):
        document = documents_by_key[key]
        retrieval_sources = sorted(source_ranks[key])
        document.metadata.update({
            "rrf_score": scores[key],
            "rrf_rank": fused_rank,
            "retrieval_sources": retrieval_sources,
            "source_ranks": source_ranks[key],
        })
        fused_documents.append(document)

    return fused_documents
