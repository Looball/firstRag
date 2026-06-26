"""检索降级与中文兜底能力的回归测试。"""

import unittest

from langchain_core.documents import Document

from app.repositories.knowledge_chunk_repository import build_search_terms
from app.services.retrieval.hybrid_retriever import get_vector_documents
from app.services.retrieval.rrf import reciprocal_rank_fusion


class FakeVectorStore:
    """模拟 Chroma 向量库，按文件过滤制造一次失败一次成功。"""

    def similarity_search_by_vector_with_relevance_scores(
        self,
        embedding: list[float],
        k: int,
        filter: dict,
    ) -> list[tuple[Document, float]]:
        """根据 file_id 决定抛错或返回测试文档。"""
        file_filter = filter["$and"][1]["file_id"]
        if file_filter == "bad-file":
            raise RuntimeError("Error finding id")

        return [
            (
                Document(
                    page_content="第二条 民事诉讼法的任务...",
                    metadata={"file_id": file_filter},
                ),
                0.1,
            )
        ]


class RetrievalResilienceTests(unittest.TestCase):
    """验证向量检索异常不会破坏全文兜底与其它文件召回。"""

    def test_chinese_query_builds_keyword_fallback_terms(self) -> None:
        """连续中文问题应提取出可命中文档的关键词片段。"""
        terms = build_search_terms("诉讼法的任务是什么")

        self.assertIn("诉讼法", terms)
        self.assertIn("任务", terms)
        self.assertNotIn("是什么", terms)

    def test_vector_search_skips_failed_file(self) -> None:
        """单个 Chroma 文件过滤查询失败时，应继续返回其它文件结果。"""
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeVectorStore(),
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]

            docs = get_vector_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["bad-file", "good-file"],
                k=5,
            )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["file_id"], "good-file")
        self.assertEqual(docs[0].metadata["retrieval_source"], "vector")

    def test_rrf_deduplicates_vector_and_fulltext_same_chunk(self) -> None:
        """同一文件同一 chunk 被两路召回时，Sources 里只应展示一次。"""
        vector_doc = Document(
            page_content="第二条 民事诉讼法的任务...",
            metadata={
                "user_id": "6",
                "file_id": "file-1",
                "chunk_index": 2,
                "retrieval_source": "vector",
            },
        )
        fulltext_doc = Document(
            page_content="第二条 民事诉讼法的任务...",
            metadata={
                "chunk_id": "6:file-1:v2:2",
                "user_id": "6",
                "file_id": "file-1",
                "chunk_index": 2,
                "retrieval_source": "fulltext",
            },
        )

        docs = reciprocal_rank_fusion([[vector_doc], [fulltext_doc]], k=5)

        self.assertEqual(len(docs), 1)
        self.assertEqual(
            docs[0].metadata["retrieval_sources"],
            ["fulltext", "vector"],
        )


if __name__ == "__main__":
    unittest.main()
