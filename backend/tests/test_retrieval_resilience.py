"""检索降级与中文兜底能力的回归测试。"""

import time
import unittest
from threading import Event
from unittest.mock import patch

from langchain_core.documents import Document

from app.repositories.knowledge_chunk_repository import build_search_terms
from app.services.cache_service import CacheBackendResult
from app.services.retrieval.hybrid_retriever import (
    QUERY_EMBEDDING_CACHE_TTL_SECONDS,
    clear_query_embedding_cache,
    expand_parent_contexts,
    get_hybrid_documents,
    get_query_embedding,
    get_query_sparse_embedding,
    get_retrieval_diagnostics,
    get_vector_documents,
    reset_retrieval_diagnostics,
)
from app.services.retrieval.reranker import (
    DashScopeQwenReranker,
    load_reranker_runtime,
)
from app.services.retrieval.rrf import reciprocal_rank_fusion
from app.services.vectors.vector_store import (
    HybridVectorSearchResponse,
    HybridVectorSearchResult,
    VectorSearchResponse,
    VectorSearchResult,
)


class FakeVectorStore:
    """模拟按单文件范围返回候选的 Milvus adapter。"""

    provider = "milvus"

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """返回符合用户和文件 scope 的测试文档。"""
        del query_embedding, k
        file_id = (file_ids or ["good-file"])[0]
        return VectorSearchResponse(results=[
            VectorSearchResult(
                Document(
                    page_content="第二条 民事诉讼法的任务...",
                    metadata={
                        "user_id": str(user_id),
                        "file_id": file_id,
                        "chunk_index": 2,
                    },
                ),
                distance=0.1,
            ),
        ])


class FakeFailingMilvusBoundary:
    """模拟通过 boundary 暴露搜索故障的 Milvus adapter。"""

    provider = "milvus"

    def search_vectors(self, **_: object) -> None:
        """模拟 Milvus 服务不可用。"""
        raise TimeoutError("Milvus unavailable")


class FakeHybridVectorStore:
    """记录 v2 hybrid boundary 参数并返回预置 child candidates。"""

    provider = "milvus"

    def __init__(self, documents: list[Document]) -> None:
        """保存返回文档和全部 hybrid 调用。"""
        self.documents = documents
        self.calls: list[dict[str, object]] = []

    def hybrid_search_vectors(self, **kwargs: object) -> HybridVectorSearchResponse:
        """返回带 provider-neutral score 的预置结果。"""
        self.calls.append(dict(kwargs))
        return HybridVectorSearchResponse(results=[
            HybridVectorSearchResult(document=document, score=1.0)
            for document in self.documents
        ])


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

    def test_milvus_failure_keeps_fulltext_and_marks_diagnostics(self) -> None:
        """Milvus 异常应保留全文结果并输出 provider-aware diagnostics。"""
        fulltext_document = Document(
            page_content="全文兜底候选",
            metadata={
                "user_id": "6",
                "file_id": "target-file",
                "chunk_index": 1,
                "retrieval_source": "fulltext",
            },
        )
        failing_store = FakeFailingMilvusBoundary()
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=failing_store,
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
            return_value=[fulltext_document],
        ):
            embedding_cls.return_value.embed_query.return_value = [0.1, 0.2]
            documents = get_hybrid_documents(
                query="索引验收标识是什么",
                user_id=6,
                file_ids=["target-file"],
                k=5,
                rerank=False,
            )

        diagnostics = get_retrieval_diagnostics()
        self.assertEqual(documents, [fulltext_document])
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["vector_degraded"])
        self.assertEqual(
            diagnostics["vector_errors"],
            ["Milvus 向量检索失败"],
        )
        self.assertIn("vector_ms", diagnostics["timing"])

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
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
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

    def test_v2_hybrid_uses_milvus_caps_children_and_expands_parents(
        self,
    ) -> None:
        """v2 path 不得调用 PG keyword，并应 child rerank 后扩展唯一 parent。"""
        children = [
            Document(
                page_content=f"child-{index}",
                metadata={
                    "user_id": 6,
                    "file_id": "file-a",
                    "chunk_id": f"child-{index}",
                    "child_id": f"child-{index}",
                    "chunk_index": index,
                    "index_version": 2,
                    "parent_id": "parent-a" if index < 3 else "parent-b",
                    "parent_index": 0 if index < 3 else 1,
                    "child_index": index if index < 3 else 0,
                    "retrieval_sources": ["dense", "sparse"],
                },
            )
            for index in range(4)
        ]
        store = FakeHybridVectorStore(children)
        parents = [
            {
                "parent_id": "parent-a",
                "file_id": "file-a",
                "index_version": 2,
                "parent_index": 0,
                "content": "完整 parent A",
                "metadata": {"page_number": 1},
            },
            {
                "parent_id": "parent-b",
                "file_id": "file-a",
                "index_version": 2,
                "parent_index": 1,
                "content": "完整 parent B",
                "metadata": {"page_number": 2},
            },
        ]
        with patch(
            "app.services.retrieval.hybrid_retriever."
            "MILVUS_DENSE_SPARSE_WRITE_ENABLED",
            True,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever."
            "get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_user_parent_chunks",
            return_value=parents,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
        ) as fulltext, patch(
            "app.services.retrieval.hybrid_retriever.get_reranker",
            return_value=FakeReranker(),
        ):
            docs = get_hybrid_documents(
                query="合同编号是什么",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                vector_k=11,
                fulltext_k=13,
                rrf_k=4,
                rerank=True,
            )

        fulltext.assert_not_called()
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(store.calls[0]["dense_k"], 11)
        self.assertEqual(store.calls[0]["sparse_k"], 13)
        self.assertEqual([doc.page_content for doc in docs], [
            "完整 parent A",
            "完整 parent B",
        ])
        self.assertEqual([doc.metadata["child_content"] for doc in docs], [
            "child-0",
            "child-3",
        ])
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertEqual(diagnostics["retrieval_mode"], "milvus_dense_sparse")
        self.assertEqual(diagnostics["parent_limited_candidate_count"], 3)
        self.assertEqual(diagnostics["parent_count"], 2)

    def test_v2_hybrid_degrades_to_dense_when_sparse_encoder_fails(self) -> None:
        """BGE-M3 sparse query 失败时仍应通过相同 boundary 做 dense-only。"""
        child = Document(
            page_content="dense child",
            metadata={
                "user_id": 6,
                "file_id": "file-a",
                "chunk_id": "child-a",
                "child_id": "child-a",
                "chunk_index": 0,
                "index_version": 2,
                "parent_id": "parent-a",
                "parent_index": 0,
                "child_index": 0,
                "retrieval_sources": ["dense"],
            },
        )
        store = FakeHybridVectorStore([child])
        with patch(
            "app.services.retrieval.hybrid_retriever."
            "MILVUS_DENSE_SPARSE_WRITE_ENABLED",
            True,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever."
            "get_query_sparse_embedding",
            side_effect=RuntimeError("encoder unavailable"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_user_parent_chunks",
            return_value=[{
                "parent_id": "parent-a",
                "file_id": "file-a",
                "index_version": 2,
                "content": "dense child",
                "metadata": {},
            }],
        ):
            docs = get_hybrid_documents(
                query="合同编号是什么",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                rerank=False,
            )

        self.assertEqual(store.calls[0]["query_sparse_embedding"], None)
        self.assertEqual(docs[0].page_content, "dense child")
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["sparse_degraded"])
        self.assertEqual(diagnostics["retrieval_sources"], ["dense"])
        self.assertEqual(diagnostics["dense_count"], 1)
        self.assertEqual(diagnostics["sparse_count"], 0)

    def test_v2_hybrid_degrades_to_sparse_when_dense_provider_fails(self) -> None:
        """用户 dense provider 失败时仍应通过相同 boundary 做 sparse-only。"""
        child = Document(
            page_content="sparse child",
            metadata={
                "user_id": 6,
                "file_id": "file-a",
                "chunk_id": "child-a",
                "child_id": "child-a",
                "chunk_index": 0,
                "index_version": 2,
                "parent_id": "parent-a",
                "parent_index": 0,
                "child_index": 0,
                "retrieval_sources": ["sparse"],
            },
        )
        store = FakeHybridVectorStore([child])
        with patch(
            "app.services.retrieval.hybrid_retriever."
            "MILVUS_DENSE_SPARSE_WRITE_ENABLED",
            True,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            side_effect=RuntimeError("provider unavailable"),
        ), patch(
            "app.services.retrieval.hybrid_retriever."
            "get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_user_parent_chunks",
            return_value=[{
                "parent_id": "parent-a",
                "file_id": "file-a",
                "index_version": 2,
                "content": "sparse child",
                "metadata": {},
            }],
        ):
            docs = get_hybrid_documents(
                query="合同编号是什么",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                rerank=False,
            )

        self.assertEqual(store.calls[0]["query_embedding"], None)
        self.assertEqual(docs[0].page_content, "sparse child")
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["dense_degraded"])
        self.assertEqual(diagnostics["retrieval_sources"], ["sparse"])
        self.assertEqual(diagnostics["dense_count"], 0)
        self.assertEqual(diagnostics["sparse_count"], 1)

    def test_v2_hybrid_failure_retries_dense_then_sparse_without_pg(self) -> None:
        """Milvus hybrid 失败只允许在同一 boundary 内按 dense/sparse 降级。"""
        child = Document(
            page_content="sparse fallback child",
            metadata={
                "user_id": 6,
                "file_id": "file-a",
                "chunk_id": "child-a",
                "child_id": "child-a",
                "chunk_index": 0,
                "index_version": 2,
                "parent_id": "parent-a",
                "parent_index": 0,
                "child_index": 0,
                "retrieval_sources": ["sparse"],
            },
        )
        response = HybridVectorSearchResponse(results=[
            HybridVectorSearchResult(document=child, score=1.0),
        ])
        store = unittest.mock.MagicMock()
        store.hybrid_search_vectors.side_effect = [
            RuntimeError("hybrid failed"),
            RuntimeError("dense failed"),
            response,
        ]
        with patch(
            "app.services.retrieval.hybrid_retriever."
            "MILVUS_DENSE_SPARSE_WRITE_ENABLED",
            True,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever."
            "get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_user_parent_chunks",
            return_value=[{
                "parent_id": "parent-a",
                "file_id": "file-a",
                "index_version": 2,
                "content": "sparse fallback child",
                "metadata": {},
            }],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_fulltext_documents",
        ) as fulltext:
            docs = get_hybrid_documents(
                query="合同编号是什么",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                rerank=False,
            )

        fulltext.assert_not_called()
        calls = store.hybrid_search_vectors.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIsNotNone(calls[0].kwargs["query_embedding"])
        self.assertIsNotNone(calls[0].kwargs["query_sparse_embedding"])
        self.assertIsNotNone(calls[1].kwargs["query_embedding"])
        self.assertIsNone(calls[1].kwargs["query_sparse_embedding"])
        self.assertIsNone(calls[2].kwargs["query_embedding"])
        self.assertIsNotNone(calls[2].kwargs["query_sparse_embedding"])
        self.assertEqual(docs[0].page_content, "sparse fallback child")
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["hybrid_degraded"])
        self.assertTrue(diagnostics["dense_degraded"])
        self.assertEqual(diagnostics["retrieval_sources"], ["sparse"])
        self.assertEqual(diagnostics["dense_count"], 0)
        self.assertEqual(diagnostics["sparse_count"], 1)

    def test_sparse_query_cache_uses_model_revision_length_and_hash(self) -> None:
        """重复 query 应复用包含 BGE-M3 identity 和 query hash 的 sparse cache。"""
        reset_retrieval_diagnostics()
        with patch(
            "app.services.retrieval.hybrid_retriever."
            "cache_service.get_json_cache",
            return_value=CacheBackendResult(hit=False),
        ), patch(
            "app.services.retrieval.hybrid_retriever."
            "cache_service.set_json_cache",
            return_value=CacheBackendResult(hit=False),
        ), patch(
            "app.services.retrieval.hybrid_retriever.SparseEncoderClient",
        ) as client_class:
            client_class.return_value.encode_query.return_value = {7: 0.75}
            first = get_query_sparse_embedding("  Hello   World  ", user_id=6)
            second = get_query_sparse_embedding("hello world", user_id=6)

        self.assertEqual(first, {7: 0.75})
        self.assertEqual(second, first)
        client_class.return_value.encode_query.assert_called_once()
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        cache_key = diagnostics["query_sparse_embedding_cache_key"]
        self.assertIn("BAAI/bge-m3", cache_key)
        self.assertIn(":1024:", cache_key)
        self.assertNotIn("hello world", cache_key)
        self.assertTrue(diagnostics["query_sparse_embedding_cache_hit"])

    def test_parent_expansion_drops_unverified_child(self) -> None:
        """PostgreSQL 缺失当前 parent 时不得把未核验 child 交给 LLM。"""
        child = Document(
            page_content="可能属于旧 index version 的 child",
            metadata={
                "user_id": 6,
                "file_id": "file-a",
                "index_version": 2,
                "parent_id": "missing-parent",
                "child_id": "child-a",
            },
        )
        reset_retrieval_diagnostics()
        with patch(
            "app.services.retrieval.hybrid_retriever.get_user_parent_chunks",
            return_value=[],
        ):
            docs = expand_parent_contexts(documents=[child], user_id=6)

        self.assertEqual(docs, [])
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["parent_context_degraded"])
        self.assertEqual(diagnostics["parent_count"], 0)

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
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
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
            "6:zhipuai:embedding-3::hello world",
        )

    def test_query_embedding_cache_can_hit_redis(self) -> None:
        """进程内缓存为空时，应能直接复用 Redis 中的 query embedding。"""
        reset_retrieval_diagnostics()
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.cache_service.get_json_cache",
            return_value=CacheBackendResult(
                hit=True,
                value=[0.3, 0.4],
            ),
        ), unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls:
            embedding = get_query_embedding("Hello World", user_id=6)

        diagnostics = get_retrieval_diagnostics()
        self.assertEqual(embedding, [0.3, 0.4])
        embedding_cls.assert_not_called()
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["query_embedding_cache_hit"])
        self.assertEqual(diagnostics["query_embedding_cache_source"], "redis")

    def test_query_embedding_cache_expires(self) -> None:
        """TTL 过期后应重新调用 embedding provider。"""
        with unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
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
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as embedding_cls, unittest.mock.patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "zhipuai", "embedding-3", ""),
        ), unittest.mock.patch(
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

    def test_missing_reranker_dependencies_raise_clear_error(self) -> None:
        """未安装 torch/transformers 时应给出可降级的明确错误。"""
        with patch(
            "app.services.retrieval.reranker.import_module",
            side_effect=ImportError("missing optional dependency"),
        ):
            with self.assertRaisesRegex(RuntimeError, "requirements-rerank"):
                load_reranker_runtime()

    def test_qwen_reranker_sorts_documents_by_remote_scores(self) -> None:
        """阿里云 Qwen rerank 应按 API 返回的 relevance score 重排。"""
        documents = [
            Document(page_content="候选 A", metadata={}),
            Document(page_content="候选 B", metadata={}),
            Document(page_content="候选 C", metadata={}),
        ]
        response = {
            "results": [
                {"index": 2, "relevance_score": 0.2},
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.5},
            ],
        }

        with patch.dict(
            "os.environ",
            {"RERANK_API_KEY": "dashscope-test-key"},
        ), patch("app.services.retrieval.reranker.OpenAI") as client_cls:
            client_cls.return_value.post.return_value = response

            reranker = DashScopeQwenReranker(
                model_name="qwen3-rerank",
                base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-api/v1",
                instruct="Retrieve semantically similar text.",
            )
            reranked = reranker.rerank(
                query="测试问题",
                documents=documents,
                top_k=2,
            )

        self.assertEqual([document.page_content for document in reranked], [
            "候选 A",
            "候选 B",
        ])
        self.assertEqual(reranked[0].metadata["rerank_score"], 0.9)
        self.assertEqual(reranked[0].metadata["rerank_rank"], 1)
        client_cls.assert_called_once_with(
            api_key="dashscope-test-key",
            base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-api/v1",
            timeout=60.0,
            max_retries=2,
        )
        client_cls.return_value.post.assert_called_once_with(
            "/reranks",
            body={
                "model": "qwen3-rerank",
                "query": "测试问题",
                "documents": ["候选 A", "候选 B", "候选 C"],
                "top_n": 2,
                "instruct": "Retrieve semantically similar text.",
            },
            cast_to=object,
        )

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
