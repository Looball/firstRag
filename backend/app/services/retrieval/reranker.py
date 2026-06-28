"""本地 Cross-Encoder 精排序。

bi-encoder 向量检索会分别编码 query 和 document，再用向量相似度做粗召回。
这种方式速度快，适合在大量 chunk 中找候选，但 query 和 document 之间
没有充分交互，因此排序精度有限。

Cross-Encoder 会把 query 和 document 拼成一对输入，同送入 Transformer，
模型可以在 token 级别同时观察问题和候选片段，输出一个相关性 logits。
它通常比 bi-encoder 排序更准确，但计算成本更高，无法直接用于全库检索。

因此本项目只在 RRF 融合后的少量候选上使用 Cross-Encoder：

    粗召回 -> RRF 融合候选 -> Cross-Encoder 精排 -> top-k 上下文

BAAI/bge-reranker-base 输出的是 raw relevance score。排序只需要比较分数
大小，因此直接使用 logits，不额外做 sigmoid。
"""

from functools import lru_cache

import torch
from langchain_core.documents import Document
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.core.config import RERANKER_MODEL_PATH


DEFAULT_RERANKER_MODEL = str(RERANKER_MODEL_PATH)
DEFAULT_RERANKER_MAX_LENGTH = 384


class LocalCrossEncoderReranker:
    """使用本地 Cross-Encoder 模型对候选文档精排序。"""

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        device: str | None = None,
    ) -> None:
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            local_files_only=True,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            local_files_only=True,
        ).to(self.device)
        self.model.eval()

    def score_documents(
        self,
        query: str,
        documents: list[Document],
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[float]:
        """计算 query 与多个文档的相关性分数。

        每个候选会以 `(query, document.page_content)` 的形式输入模型。
        返回值是模型 logits，值越大表示候选和问题越相关。
        """
        scores: list[float] = []

        for start in range(0, len(documents), batch_size):
            batch_documents = documents[start:start + batch_size]
            features = self.tokenizer(
                [query] * len(batch_documents),
                [document.page_content for document in batch_documents],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            features = {
                name: value.to(self.device)
                for name, value in features.items()
            }

            with torch.no_grad():
                logits = self.model(**features).logits

            # BGE reranker 输出 raw relevance score；排序时直接使用 logits。
            batch_scores = logits.view(-1).detach().cpu().float().tolist()
            scores.extend(batch_scores)

        return scores

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        batch_size: int = 8,
        max_length: int = DEFAULT_RERANKER_MAX_LENGTH,
    ) -> list[Document]:
        """返回按 Cross-Encoder 分数重排后的 top_k 文档。"""
        if not documents:
            return []

        scores = self.score_documents(
            query=query,
            documents=documents,
            batch_size=batch_size,
            max_length=max_length,
        )

        for document, score in zip(documents, scores, strict=True):
            document.metadata["rerank_score"] = score

        reranked_documents = sorted(
            documents,
            key=lambda document: document.metadata["rerank_score"],
            reverse=True,
        )
        for rank, document in enumerate(reranked_documents, start=1):
            document.metadata["rerank_rank"] = rank

        return reranked_documents[:top_k]


@lru_cache(maxsize=1)
def get_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> LocalCrossEncoderReranker:
    """缓存本地 reranker，避免每次检索重复加载模型。"""
    return LocalCrossEncoderReranker(model_name=model_name)
