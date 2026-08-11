"""Milvus current-data acceptance 汇总逻辑测试。"""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.services.vectors.chroma_to_milvus_migration import (
    MigrationChunkFact,
    MigrationFilePlan,
)
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
)
from app.services.vectors.milvus_acceptance import percentile, run_acceptance
from app.services.vectors.vector_store import (
    VectorRecord,
    VectorSearchResponse,
    VectorSearchResult,
)


class FakeAcceptanceStore:
    """返回固定 current record，并对错误 user/file scope 返回空集。"""

    def __init__(self, record: VectorRecord, user_id: int, file_id: str) -> None:
        """保存唯一允许检索的用户和文件范围。"""
        self.record = record
        self.user_id = user_id
        self.file_id = file_id

    def list_file_vectors(self, **_kwargs: object) -> list[VectorRecord]:
        """返回一条包含 embedding 的审计记录。"""
        return [self.record]

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """仅在正确 scalar scope 返回 top-1 self-hit。"""
        del query_embedding, k
        if user_id != self.user_id or file_ids != [self.file_id]:
            return VectorSearchResponse()
        result_document = Document(
            page_content=self.record.document.page_content,
            metadata={
                **self.record.document.metadata,
                "chunk_id": self.record.id,
            },
        )
        return VectorSearchResponse(results=[VectorSearchResult(
            document=result_document,
            distance=0.0,
        )])


class MilvusAcceptanceTests(unittest.TestCase):
    """验证 percentile、current 对账、隔离和延迟门禁。"""

    def test_percentile_uses_nearest_rank(self) -> None:
        """P95 小样本必须取 nearest-rank，而不是静默插值。"""
        self.assertEqual(percentile([1, 2, 3, 4], 95), 4)
        with self.assertRaises(ValueError):
            percentile([], 95)

    def test_run_acceptance_passes_complete_single_collection_scope(self) -> None:
        """完整对账、10 次 self-hit 和两项隔离检查应通过。"""
        user_id = 7
        file_id = "00000000-0000-0000-0000-000000000136"
        chunk_id = f"{user_id}:{file_id}:v1:0"
        metadata = {
            "user_id": user_id,
            "file_id": file_id,
            "chunk_index": 0,
            "index_version": 1,
        }
        record = VectorRecord(
            id=chunk_id,
            document=Document(page_content="acceptance", metadata=metadata),
            embedding=[1.0, 0.0],
        )
        plan = MigrationFilePlan(
            user_id=user_id,
            file_id=file_id,
            file_status="indexed",
            file_index_version=1,
            settings=EmbeddingModelSettings(
                provider="openai_compatible",
                model="acceptance",
                api_key="",
                base_url=None,
                dimensions=2,
                timeout_seconds=10,
                max_retries=0,
            ),
            source_collection="source",
            target_collection="target",
            chunks=(MigrationChunkFact(
                chunk_id=chunk_id,
                user_id=user_id,
                file_id=file_id,
                index_version=1,
                chunk_index=0,
                content="acceptance",
                metadata=metadata,
            ),),
        )
        store = FakeAcceptanceStore(record, user_id, file_id)
        pair = SimpleNamespace(source=store, target=store, close=lambda: None)

        with (
            patch(
                "app.services.vectors.milvus_acceptance."
                "list_vector_migration_chunk_rows",
                return_value=[{}],
            ),
            patch(
                "app.services.vectors.milvus_acceptance."
                "build_migration_file_plans",
                return_value=[plan],
            ),
            patch(
                "app.services.vectors.milvus_acceptance._create_store_pair",
                return_value=pair,
            ),
        ):
            report = run_acceptance(
                iterations=10,
                top_k=1,
                warmed_p95_threshold_ms=50,
            )

        self.assertTrue(report["passed"])
        self.assertEqual(report["verified"]["self_hits"], 10)
        self.assertEqual(report["verified"]["isolation_checks"], 2)
        self.assertEqual(report["verified"]["minimum_top_k_overlap"], 1.0)
        self.assertLessEqual(report["warmed_filtered_ann"]["p95_ms"], 50)


if __name__ == "__main__":
    unittest.main()
