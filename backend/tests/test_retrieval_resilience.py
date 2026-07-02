"""检索降级与中文兜底能力的回归测试。"""

import time
import unittest
from threading import Event

from langchain_core.documents import Document

from app.repositories.knowledge_chunk_repository import build_search_terms
from app.services.retrieval.hybrid_retriever import (
    QUERY_EMBEDDING_CACHE_TTL_SECONDS,
    clear_query_embedding_cache,
    get_hybrid_documents,
    get_retrieval_diagnostics,
    get_vector_documents,
)
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
                    metadata={
                        "user_id": "6",
                        "file_id": file_filter,
                        "chunk_index": 2,
                    },
                ),
                0.1,
            )
        ]


class FakeFallbackVectorStore:
    """模拟单文件过滤失败但用户级过滤可命中的 Chroma 向量库。"""

    def similarity_search_by_vector_with_relevance_scores(
        self,
        embedding: list[float],
        k: int,
        filter: dict,
    ) -> list[tuple[Document, float]]:
        """单文件过滤抛错，用户级过滤返回待后过滤候选。"""
        if "$and" in filter:
            raise RuntimeError("Error finding id")

        return [
            (
                Document(
                    page_content="目标文件向量候选",
                    metadata={
                        "user_id": "6",
                        "file_id": "target-file",
                        "chunk_index": 1,
                    },
                ),
                0.1,
            ),
            (
                Document(
                    page_content="其它文件向量候选",
                    metadata={
                        "user_id": "6",
                        "file_id": "other-file",
                        "chunk_index": 1,
                    },
                ),
                0.2,
            ),
        ]


class FakeReranker:
    """模拟 CrossEncoder reranker，避免单元测试加载真实模型。"""

    def __init__(self) -> None:
        """记录最近一次调用参数，便于测试性能配置。"""
        self.last_max_length: int | None = None

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int,
        batch_size: int = 8,
        max_length: int = 384,
    ) -> list[Document]:
        """返回前 top_k 个文档，并写入测试用 rerank 分数。"""
        self.last_max_length = max_length
        for index, document in enumerate(documents, start=1):
            document.metadata["rerank_score"] = float(index)
        return documents[:top_k]


class RetrievalResilienceTests(unittest.TestCase):
    """验证向量检索异常不会破坏全文兜底与其它文件召回。"""

    def setUp(self) -> None:
        """清空进程内缓存，保证用例彼此独立。"""
        clear_query_embedding_cache()

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

    def test_vector_search_retries_user_scope_after_file_filter_failure(
        self,
    ) -> None:
        """单文件过滤触发 Chroma HNSW 错误时，应退回用户级检索后过滤。"""
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeFallbackVectorStore(),
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]

            docs = get_vector_documents(
                query="索引验收标识是什么",
                user_id=6,
                file_ids=["target-file"],
                k=5,
            )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["file_id"], "target-file")
        self.assertEqual(docs[0].metadata["retrieval_source"], "vector")

    def test_hybrid_retrieval_skips_rerank_when_candidates_fit_top_k(
        self,
    ) -> None:
        """候选数不超过最终 top_k 时应跳过昂贵的 CrossEncoder。"""
        fulltext_doc = Document(
            page_content="第二条 民事诉讼法的任务...",
            metadata={
                "user_id": "6",
                "file_id": "good-file",
                "chunk_index": 2,
                "retrieval_source": "fulltext",
            },
        )
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeVectorStore(),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=[fulltext_doc],
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_reranker",
            return_value=FakeReranker(),
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]

            docs = get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(len(docs), 1)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        timing = diagnostics["timing"]
        for key in (
            "embedding_ms",
            "vector_ms",
            "fulltext_ms",
            "rrf_ms",
            "retrieval_total_ms",
        ):
            self.assertIn(key, timing)
            self.assertIsInstance(timing[key], float)
            self.assertGreaterEqual(timing[key], 0.0)
        self.assertNotIn("rerank_ms", timing)
        self.assertEqual(diagnostics["reranked_count"], 0)
        self.assertTrue(diagnostics["rerank_skipped"])
        self.assertEqual(
            diagnostics["rerank_skip_reason"],
            "candidate_count_not_above_top_k",
        )

    def test_hybrid_retrieval_records_rerank_timing_when_needed(self) -> None:
        """候选数超过最终 top_k 时仍应执行并记录 rerank 耗时。"""
        vector_docs = [
            Document(
                page_content=f"向量候选 {index}",
                metadata={
                    "user_id": "6",
                    "file_id": f"vector-file-{index}",
                    "chunk_index": index,
                    "retrieval_source": "vector",
                },
            )
            for index in range(3)
        ]
        fulltext_docs = [
            Document(
                page_content=f"全文候选 {index}",
                metadata={
                    "user_id": "6",
                    "file_id": f"fulltext-file-{index}",
                    "chunk_index": index,
                    "retrieval_source": "fulltext",
                },
            )
            for index in range(3)
        ]

        fake_reranker = FakeReranker()
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_documents",
            return_value=vector_docs,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=fulltext_docs,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_reranker",
            return_value=fake_reranker,
        ):
            docs = get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=2,
                rrf_k=6,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(len(docs), 2)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertEqual(diagnostics["reranked_count"], 2)
        self.assertEqual(fake_reranker.last_max_length, 384)
        self.assertIn("rerank_ms", diagnostics["timing"])
        self.assertFalse(diagnostics.get("rerank_skipped", False))

    def test_hybrid_retrieval_falls_back_when_rerank_fails(self) -> None:
        """rerank 异常应降级为 RRF 结果并写入可观测日志。"""
        vector_docs = [
            Document(
                page_content=f"向量候选 {index}",
                metadata={
                    "user_id": "6",
                    "file_id": f"vector-file-{index}",
                    "chunk_index": index,
                    "retrieval_source": "vector",
                },
            )
            for index in range(3)
        ]
        fulltext_docs = [
            Document(
                page_content=f"全文候选 {index}",
                metadata={
                    "user_id": "6",
                    "file_id": f"fulltext-file-{index}",
                    "chunk_index": index,
                    "retrieval_source": "fulltext",
                },
            )
            for index in range(3)
        ]

        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_documents",
            return_value=vector_docs,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=fulltext_docs,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_reranker",
            side_effect=RuntimeError("CrossEncoder rerank failed"),
        ), self.assertLogs(
            "app.services.retrieval.hybrid_retriever",
            level="ERROR",
        ) as logs:
            docs = get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=2,
                rrf_k=6,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(len(docs), 2)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["rerank_degraded"])
        self.assertEqual(diagnostics["rerank_errors"], ["rerank 精排失败"])
        self.assertIn("rerank_ms", diagnostics["timing"])
        self.assertIn("retrieval_total_ms", diagnostics["timing"])
        self.assertIn("retrieval_rerank_failed", logs.records[0].getMessage())
        self.assertIn("rerank", logs.records[0].getMessage())

    def test_hybrid_retrieval_keeps_vector_results_when_fulltext_fails(
        self,
    ) -> None:
        """全文粗召回失败时，向量结果仍应作为兜底返回。"""
        vector_doc = Document(
            page_content="向量候选",
            metadata={
                "user_id": "6",
                "file_id": "vector-file",
                "chunk_index": 1,
                "retrieval_source": "vector",
            },
        )

        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_documents",
            return_value=[vector_doc],
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            side_effect=RuntimeError("postgres timeout"),
        ):
            docs = get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(docs, [vector_doc])
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertEqual(diagnostics["vector_count"], 1)
        self.assertEqual(diagnostics["fulltext_count"], 0)
        self.assertTrue(diagnostics["fulltext_degraded"])
        self.assertEqual(diagnostics["fulltext_errors"], ["全文粗召回失败"])
        self.assertIn("fulltext_ms", diagnostics["timing"])

    def test_query_embedding_cache_hits_for_repeated_query(self) -> None:
        """TTL 内重复 query 应复用缓存的 query embedding。"""
        fulltext_doc = Document(
            page_content="全文候选",
            metadata={
                "user_id": "6",
                "file_id": "good-file",
                "chunk_index": 1,
                "retrieval_source": "fulltext",
            },
        )

        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeVectorStore(),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=[fulltext_doc],
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]

            get_hybrid_documents(
                query="  Hello   World  ",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )
            get_hybrid_documents(
                query="hello world",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        embedding_cls.return_value.embed_query.assert_called_once()
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["query_embedding_cache_hit"])
        self.assertEqual(
            diagnostics["query_embedding_cache_key"],
            "zhipuai:embedding-3:hello world",
        )

    def test_query_embedding_cache_expires(self) -> None:
        """TTL 过期后应重新调用 embedding provider。"""
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeVectorStore(),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=[],
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.monotonic",
            side_effect=[
                100.0,
                100.0 + QUERY_EMBEDDING_CACHE_TTL_SECONDS + 1,
            ],
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]

            get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )
            get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(embedding_cls.return_value.embed_query.call_count, 2)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertFalse(diagnostics["query_embedding_cache_hit"])

    def test_query_embedding_failure_does_not_pollute_cache(self) -> None:
        """embedding 生成失败不应写入缓存，后续请求仍可重试。"""
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.ZhipuAIEmbeddings",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=FakeVectorStore(),
        ):
            embedding_cls.return_value.embed_query.side_effect = [
                RuntimeError("embedding timeout"),
                [0.1, 0.2],
            ]

            failed_docs = get_vector_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
            )
            retried_docs = get_vector_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
            )

        self.assertEqual(failed_docs, [])
        self.assertEqual(len(retried_docs), 1)
        self.assertEqual(embedding_cls.return_value.embed_query.call_count, 2)

    def test_hybrid_retrieval_runs_coarse_recall_in_parallel(self) -> None:
        """vector 和 fulltext 粗召回应并行执行，避免串行等待。"""
        vector_started = Event()
        fulltext_started = Event()
        vector_observed_fulltext = False
        fulltext_observed_vector = False

        def fake_vector_documents(*args, **kwargs) -> list[Document]:
            nonlocal vector_observed_fulltext
            vector_started.set()
            vector_observed_fulltext = fulltext_started.wait(timeout=1)
            time.sleep(0.02)
            return []

        def fake_fulltext_documents(*args, **kwargs) -> list[Document]:
            nonlocal fulltext_observed_vector
            fulltext_started.set()
            fulltext_observed_vector = vector_started.wait(timeout=1)
            time.sleep(0.02)
            return []

        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_documents",
            side_effect=fake_vector_documents,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            side_effect=fake_fulltext_documents,
        ):
            docs = get_hybrid_documents(
                query="诉讼法的任务是什么",
                user_id=6,
                file_ids=["good-file"],
                k=5,
                rerank=True,
            )

        diagnostics = get_retrieval_diagnostics()

        self.assertEqual(docs, [])
        self.assertTrue(vector_started.is_set())
        self.assertTrue(fulltext_started.is_set())
        self.assertTrue(vector_observed_fulltext)
        self.assertTrue(fulltext_observed_vector)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertIn("fulltext_ms", diagnostics["timing"])

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
