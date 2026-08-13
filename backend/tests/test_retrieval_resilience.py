"""Milvus-only dense/sparse 检索降级与上下文回归测试。"""

import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from app.services.cache_service import CacheBackendResult
from app.services.retrieval.hybrid_retriever import (
    clear_query_embedding_cache,
    expand_parent_contexts,
    get_hybrid_documents,
    get_query_embedding,
    get_query_sparse_embedding,
    get_retrieval_diagnostics,
    reset_retrieval_diagnostics,
)
from app.services.vectors.vector_store import (
    HybridVectorSearchResponse,
    HybridVectorSearchResult,
)


def build_child(
    *,
    child_id: str,
    parent_id: str,
    child_content: str,
    parent_content: str,
    sources: list[str],
) -> Document:
    """构造携带 Milvus parent 文本的测试 child。"""
    return Document(
        page_content=child_content,
        metadata={
            "user_id": 6,
            "file_id": "file-a",
            "chunk_id": child_id,
            "child_id": child_id,
            "chunk_index": int(child_id.rsplit("-", 1)[-1]),
            "index_version": 3,
            "parent_id": parent_id,
            "parent_index": 0 if parent_id == "parent-a" else 1,
            "child_index": 0,
            "parent_content": parent_content,
            "retrieval_sources": sources,
        },
    )


class FakeHybridStore:
    """记录 Milvus hybrid boundary 调用并返回预置结果。"""

    provider = "milvus"

    def __init__(self, documents: list[Document]) -> None:
        """保存待返回 documents。"""
        self.documents = documents
        self.calls: list[dict[str, object]] = []

    def hybrid_search_vectors(self, **kwargs: object) -> HybridVectorSearchResponse:
        """记录参数并返回融合候选。"""
        self.calls.append(kwargs)
        return HybridVectorSearchResponse(results=[
            HybridVectorSearchResult(document=document, score=1.0)
            for document in self.documents
        ])


class RetrievalResilienceTests(unittest.TestCase):
    """验证 PostgreSQL 退出后 Milvus 检索、降级和上下文行为。"""

    def setUp(self) -> None:
        """清空 query caches。"""
        clear_query_embedding_cache()

    def test_hybrid_returns_milvus_parent_text_without_postgres(self) -> None:
        """命中 child 后应直接把 entity 中 parent 文本交给 LLM。"""
        store = FakeHybridStore([
            build_child(
                child_id="child-0",
                parent_id="parent-a",
                child_content="精确 child A",
                parent_content="完整 parent A",
                sources=["dense", "sparse"],
            ),
            build_child(
                child_id="child-1",
                parent_id="parent-b",
                child_content="精确 child B",
                parent_content="完整 parent B",
                sources=["dense", "sparse"],
            ),
        ])
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="合同编号",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                rerank=False,
            )

        self.assertEqual(
            [document.page_content for document in documents],
            ["完整 parent A", "完整 parent B"],
        )
        self.assertEqual(
            [document.metadata["child_content"] for document in documents],
            ["精确 child A", "精确 child B"],
        )
        self.assertNotIn("parent_content", documents[0].metadata)
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertEqual(diagnostics["retrieval_mode"], "milvus_dense_sparse")
        self.assertEqual(diagnostics["parent_count"], 2)

    def test_sparse_failure_degrades_to_dense_only(self) -> None:
        """BGE-M3 query 失败时只在 Milvus 内降级为 dense。"""
        store = FakeHybridStore([build_child(
            child_id="child-0",
            parent_id="parent-a",
            child_content="dense child",
            parent_content="dense parent",
            sources=["dense"],
        )])
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            side_effect=RuntimeError("encoder unavailable"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                rerank=False,
            )

        self.assertIsNone(store.calls[0]["query_sparse_embedding"])
        self.assertEqual(documents[0].page_content, "dense parent")
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["sparse_degraded"])
        self.assertEqual(diagnostics["retrieval_sources"], ["dense"])

    def test_dense_failure_degrades_to_sparse_only(self) -> None:
        """用户 dense provider 失败时仍可使用 Milvus sparse route。"""
        store = FakeHybridStore([build_child(
            child_id="child-0",
            parent_id="parent-a",
            child_content="sparse child",
            parent_content="sparse parent",
            sources=["sparse"],
        )])
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            side_effect=RuntimeError("provider unavailable"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                rerank=False,
            )

        self.assertIsNone(store.calls[0]["query_embedding"])
        self.assertEqual(documents[0].page_content, "sparse parent")
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["dense_degraded"])
        self.assertEqual(diagnostics["retrieval_sources"], ["sparse"])

    def test_missing_parent_text_is_dropped(self) -> None:
        """缺少 Milvus parent_content 的 child 不能进入 LLM context。"""
        reset_retrieval_diagnostics()
        child = build_child(
            child_id="child-0",
            parent_id="parent-a",
            child_content="child",
            parent_content="",
            sources=["dense"],
        )
        documents = expand_parent_contexts(documents=[child], user_id=6)

        self.assertEqual(documents, [])
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["parent_context_degraded"])

    def test_hybrid_failure_falls_back_to_dense_without_postgres(self) -> None:
        """Milvus hybrid 异常后应在原 scalar scope 内尝试 dense-only。"""
        dense_child = build_child(
            child_id="child-0",
            parent_id="parent-a",
            child_content="dense child",
            parent_content="dense parent",
            sources=["dense"],
        )
        store = Mock()
        store.hybrid_search_vectors.side_effect = [
            RuntimeError("hybrid unavailable"),
            HybridVectorSearchResponse(results=[
                HybridVectorSearchResult(document=dense_child, score=1.0),
            ]),
        ]
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                rerank=False,
            )

        self.assertEqual(documents[0].page_content, "dense parent")
        self.assertEqual(store.hybrid_search_vectors.call_count, 2)
        dense_fallback = store.hybrid_search_vectors.call_args_list[1].kwargs
        self.assertEqual(dense_fallback["file_ids"], ["file-a"])
        self.assertIsNone(dense_fallback["query_sparse_embedding"])
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["hybrid_degraded"])
        self.assertTrue(diagnostics["sparse_degraded"])

    def test_hybrid_and_dense_failure_fall_back_to_sparse(self) -> None:
        """Hybrid 与 dense-only 均失败时应尝试同范围 sparse-only。"""
        sparse_child = build_child(
            child_id="child-0",
            parent_id="parent-a",
            child_content="sparse child",
            parent_content="sparse parent",
            sources=["sparse"],
        )
        store = Mock()
        store.hybrid_search_vectors.side_effect = [
            RuntimeError("hybrid unavailable"),
            RuntimeError("dense unavailable"),
            HybridVectorSearchResponse(results=[
                HybridVectorSearchResult(document=sparse_child, score=1.0),
            ]),
        ]
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                rerank=False,
            )

        self.assertEqual(documents[0].page_content, "sparse parent")
        sparse_fallback = store.hybrid_search_vectors.call_args_list[2].kwargs
        self.assertEqual(sparse_fallback["file_ids"], ["file-a"])
        self.assertIsNone(sparse_fallback["query_embedding"])
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["dense_degraded"])

    def test_rerank_failure_preserves_milvus_rrf_order(self) -> None:
        """Reranker 故障时应保留 Milvus RRF 结果与 parent 文本。"""
        store = FakeHybridStore([
            build_child(
                child_id="child-0",
                parent_id="parent-a",
                child_content="child A",
                parent_content="parent A",
                sources=["dense", "sparse"],
            ),
            build_child(
                child_id="child-1",
                parent_id="parent-b",
                child_content="child B",
                parent_content="parent B",
                sources=["dense", "sparse"],
            ),
        ])
        reranker = Mock()
        reranker.rerank.side_effect = RuntimeError("reranker unavailable")
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_reranker",
            return_value=reranker,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                rerank=True,
            )

        self.assertEqual(
            [document.page_content for document in documents],
            ["parent A", "parent B"],
        )
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertTrue(diagnostics["rerank_degraded"])

    def test_parent_candidate_cap_and_unique_context(self) -> None:
        """同一 parent 的多个 child 不应挤占最终 parent context 数量。"""
        store = FakeHybridStore([
            build_child(
                child_id=f"child-{index}",
                parent_id="parent-a" if index < 3 else "parent-b",
                child_content=f"child {index}",
                parent_content="parent A" if index < 3 else "parent B",
                sources=["dense", "sparse"],
            )
            for index in range(4)
        ])
        with patch(
            "app.services.retrieval.hybrid_retriever.get_query_embedding",
            return_value=[0.1, 0.2],
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_query_sparse_embedding",
            return_value={7: 0.9},
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_vector_store",
            return_value=store,
        ):
            documents = get_hybrid_documents(
                query="制度",
                user_id=6,
                file_ids=["file-a"],
                k=2,
                rerank=False,
            )

        self.assertEqual(
            [document.page_content for document in documents],
            ["parent A", "parent B"],
        )
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertEqual(diagnostics["parent_limited_candidate_count"], 3)

    def test_dense_query_cache_reuses_provider_result(self) -> None:
        """重复 query 应复用 dense embedding cache。"""
        embedding_model = Mock()
        embedding_model.embed_query.return_value = [0.1, 0.2]
        with patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
            return_value=embedding_model,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "qwen", "embedding", "1024"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.get_json_cache",
            return_value=CacheBackendResult(hit=False),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.set_json_cache",
            return_value=CacheBackendResult(hit=False),
        ):
            first = get_query_embedding("同一问题", 6)
            second = get_query_embedding("同一问题", 6)

        self.assertEqual(first, second)
        embedding_model.embed_query.assert_called_once_with("同一问题")

    def test_sparse_query_cache_key_excludes_plaintext(self) -> None:
        """sparse cache identity 应使用 query hash，不保存 query 明文。"""
        reset_retrieval_diagnostics()
        encoder = Mock()
        encoder.encode_query.return_value = {9: 0.8}
        with patch(
            "app.services.retrieval.hybrid_retriever.SparseEncoderClient",
            return_value=encoder,
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.get_json_cache",
            return_value=CacheBackendResult(hit=False),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.set_json_cache",
            return_value=CacheBackendResult(hit=False),
        ):
            result = get_query_sparse_embedding("企业内部机密问题", 6)

        self.assertEqual(result, {9: 0.8})
        diagnostics = get_retrieval_diagnostics()
        assert diagnostics is not None
        self.assertNotIn(
            "企业内部机密问题",
            diagnostics["query_sparse_embedding_cache_key"],
        )

    def test_dense_query_cache_can_hit_redis_without_provider(self) -> None:
        """Redis 中的合法 dense vector 应避免再次调用远程 provider。"""
        with patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "qwen", "embedding", "1024"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.get_json_cache",
            return_value=CacheBackendResult(hit=True, value=[0.3, 0.4]),
        ), patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
        ) as create_model:
            embedding = get_query_embedding("同一问题", 6)

        self.assertEqual(embedding, [0.3, 0.4])
        create_model.assert_not_called()

    def test_dense_query_failure_does_not_pollute_memory_cache(self) -> None:
        """Provider 失败不能写入 cache，下一次请求仍应真实重试。"""
        embedding_model = Mock()
        embedding_model.embed_query.side_effect = [
            RuntimeError("provider unavailable"),
            [0.1, 0.2],
        ]
        with patch(
            "app.services.retrieval.hybrid_retriever.create_embedding_model",
            return_value=embedding_model,
        ), patch(
            "app.services.retrieval.hybrid_retriever.get_embedding_cache_identity",
            return_value=("6", "qwen", "embedding", "1024"),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.get_json_cache",
            return_value=CacheBackendResult(hit=False),
        ), patch(
            "app.services.retrieval.hybrid_retriever.cache_service.set_json_cache",
            return_value=CacheBackendResult(hit=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                get_query_embedding("重试问题", 6)
            embedding = get_query_embedding("重试问题", 6)

        self.assertEqual(embedding, [0.1, 0.2])
        self.assertEqual(embedding_model.embed_query.call_count, 2)


if __name__ == "__main__":
    unittest.main()
