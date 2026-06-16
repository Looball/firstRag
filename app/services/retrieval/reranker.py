from functools import lru_cache

import torch
from langchain_core.documents import Document
from transformers import AutoModelForSequenceClassification, AutoTokenizer


DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"


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
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
        ).to(self.device)
        self.model.eval()

    def score_documents(
        self,
        query: str,
        documents: list[Document],
        batch_size: int = 8,
        max_length: int = 512,
    ) -> list[float]:
        """计算 query 与多个文档的相关性分数。"""
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
        max_length: int = 512,
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
