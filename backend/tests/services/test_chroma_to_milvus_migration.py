"""Chroma 到 Milvus 可恢复迁移工具测试。"""

import argparse
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.services.vectors.chroma_to_milvus_migration import (
    MigrationOptions,
    MigrationStorePair,
    MigrationValidationError,
    _validate_args,
    build_migration_file_plans,
    main,
    run_migration,
    validate_backup_manifest,
    validate_source_records,
)
from app.services.vectors.milvus_vector_store import MilvusVectorStore
from app.services.vectors.vector_store import (
    VectorRecord,
    VectorSearchResponse,
    VectorSearchResult,
    VectorStoreHealth,
)
from tests.services.test_milvus_vector_store import FakeMilvusClient


def _cosine(left: list[float], right: list[float]) -> float:
    """计算测试 source ANN 的 cosine similarity。"""
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot_product / (left_norm * right_norm)


class FakeSourceStore:
    """只读、用户/文件隔离的 Chroma source fake。"""

    provider = "chroma"
    collection_name = "langchain-u1-identity"

    def __init__(self, records: list[VectorRecord]) -> None:
        """保存 source records 并跟踪任何意外 mutation。"""
        self.records = records
        self.mutations = 0

    def ensure_collection(self) -> str:
        """返回 fake collection name。"""
        return self.collection_name

    def replace_file_vectors(self, **_: object) -> None:
        """记录不应发生的 source mutation。"""
        self.mutations += 1

    def delete_file_vectors(self, **_: object) -> None:
        """记录不应发生的 source mutation。"""
        self.mutations += 1

    def list_file_vectors(
        self,
        *,
        user_id: int,
        file_id: str,
        include_embeddings: bool = False,
    ) -> list[VectorRecord]:
        """按 scope 返回 source records。"""
        del include_embeddings
        return [
            record
            for record in self.records
            if str(record.document.metadata["user_id"]) == str(user_id)
            and str(record.document.metadata["file_id"]) == str(file_id)
        ]

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """以真实 cosine 排序模拟 Chroma stored-vector search。"""
        allowed = set(file_ids or [])
        records = [
            record
            for record in self.records
            if str(record.document.metadata["user_id"]) == str(user_id)
            and (
                not allowed
                or str(record.document.metadata["file_id"]) in allowed
            )
        ]
        ranked = sorted(
            records,
            key=lambda record: _cosine(query_embedding, record.embedding or []),
            reverse=True,
        )[:k]
        return VectorSearchResponse(results=[
            VectorSearchResult(
                document=record.document,
                distance=1.0 - _cosine(query_embedding, record.embedding or []),
            )
            for record in ranked
        ])

    def count_vectors(self, **_: object) -> int:
        """返回 fake 总数。"""
        return len(self.records)

    def health_check(self) -> VectorStoreHealth:
        """返回健康状态。"""
        return VectorStoreHealth(
            healthy=True,
            provider=self.provider,
            collection_name=self.collection_name,
        )


def _rows() -> list[dict[str, object]]:
    """创建两个 current PostgreSQL chunk facts。"""
    return [
        {
            "chunk_id": f"1:file-a:v2:{index}",
            "user_id": 1,
            "file_id": "file-a",
            "index_version": 2,
            "chunk_index": index,
            "content": f"chunk-{index}",
            "metadata": {
                "user_id": "1",
                "file_id": "file-a",
                "chunk_index": index,
                "index_version": 2,
                "page_number": index + 1,
            },
            "file_index_version": 2,
            "file_status": "indexed",
            "embedding_provider": "qwen",
            "embedding_model": "text-embedding-v4",
            "embedding_dimensions": 2,
            "embedding_timeout_seconds": 60,
            "embedding_max_retries": 2,
        }
        for index in range(2)
    ]


def _records() -> list[VectorRecord]:
    """创建与 PostgreSQL facts 一致的 Chroma records。"""
    embeddings = ([1.0, 0.0], [0.0, 1.0])
    return [
        VectorRecord(
            id=str(row["chunk_id"]),
            document=Document(
                page_content=str(row["content"]),
                metadata=dict(row["metadata"]),
            ),
            embedding=list(embeddings[index]),
        )
        for index, row in enumerate(_rows())
    ]


class MigrationHarness:
    """在多次 run 之间复用同一个 Milvus fake，验证 resume 幂等性。"""

    def __init__(self, source: FakeSourceStore) -> None:
        """初始化 source、target client 与 close 计数。"""
        self.source = source
        self.client = FakeMilvusClient()
        self.close_calls = 0

    def pair(self, plan) -> MigrationStorePair:
        """为计划创建不含 embedding provider 的 target adapter。"""
        target = MilvusVectorStore(
            client=self.client,
            collection_name=str(plan.target_collection),
            user_collection_prefix="firstrag_u1_",
            embedding_model=None,
            dimensions=2,
            timeout_seconds=10,
            consistency_level="Strong",
        )
        return MigrationStorePair(
            source=self.source,
            target=target,
            close=self._close,
        )

    def _close(self) -> None:
        """记录 context 已释放。"""
        self.close_calls += 1


class ChromaToMilvusMigrationTests(unittest.TestCase):
    """验证 dry-run、resume、失败清单和 rollback 只读边界。"""

    def setUp(self) -> None:
        """创建隔离的 checkpoint/report 目录。"""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.plans = build_migration_file_plans(_rows())

    def tearDown(self) -> None:
        """清理临时文件。"""
        self.temporary_directory.cleanup()

    def _options(
        self,
        *,
        dry_run: bool = False,
        rollback_check: bool = False,
    ) -> MigrationOptions:
        """创建测试运行参数。"""
        return MigrationOptions(
            dry_run=dry_run,
            rollback_check=rollback_check,
            batch_size=1,
            sleep_seconds=0,
            sample_top_k=2,
            checkpoint_path=self.root / "checkpoint.json",
            report_path=self.root / "report.json",
        )

    def test_dry_run_validates_source_without_writing_target_or_checkpoint(self) -> None:
        """dry-run 只写报告，不创建 Milvus collection 或 checkpoint。"""
        harness = MigrationHarness(FakeSourceStore(_records()))

        report = run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=self._options(dry_run=True),
        )

        self.assertEqual(report["summary"]["files_completed"], 1)
        self.assertFalse(harness.client.collections)
        self.assertFalse((self.root / "checkpoint.json").exists())
        self.assertTrue((self.root / "report.json").exists())
        self.assertEqual(harness.source.mutations, 0)

    def test_migrate_preserves_vectors_and_resume_does_not_upsert_again(self) -> None:
        """真实导入保留数据，重复运行通过 checkpoint 验证后跳过 mutation。"""
        harness = MigrationHarness(FakeSourceStore(_records()))
        options = self._options()

        first = run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=options,
            backup_evidence={"manifest_sha256": "abc"},
        )
        first_upsert_calls = harness.client.upsert_calls
        second = run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=options,
            backup_evidence={"manifest_sha256": "abc"},
        )

        self.assertEqual(first["summary"]["files_failed"], 0)
        self.assertEqual(second["summary"]["files_resumed_verified"], 1)
        self.assertEqual(harness.client.upsert_calls, first_upsert_calls)
        self.assertEqual(harness.source.mutations, 0)
        checkpoint = json.loads((self.root / "checkpoint.json").read_text())
        self.assertEqual(checkpoint["files"]["1:file-a"]["status"], "completed")

    def test_source_failure_is_machine_readable_and_requests_reindex(self) -> None:
        """缺失 embedding 不得静默跳过，报告必须给出稳定失败 code。"""
        records = _records()
        records[0] = VectorRecord(
            id=records[0].id,
            document=records[0].document,
            embedding=None,
        )
        harness = MigrationHarness(FakeSourceStore(records))

        report = run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=self._options(dry_run=True),
        )

        self.assertEqual(report["summary"]["files_failed"], 1)
        self.assertEqual(report["failures"][0]["code"], "chroma_embedding_missing")
        self.assertEqual(
            report["reindex_required"][0]["reason"],
            "chroma_embedding_missing",
        )

    def test_rollback_check_verifies_ann_and_does_not_mutate_either_store(self) -> None:
        """rollback-check 只读验证 Chroma fingerprint 和 filtered ANN。"""
        harness = MigrationHarness(FakeSourceStore(_records()))

        report = run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=self._options(rollback_check=True),
        )

        self.assertEqual(report["files"][0]["status"], "rollback_ready")
        self.assertTrue(report["files"][0]["source_unchanged"])
        self.assertFalse(harness.client.collections)
        self.assertEqual(harness.source.mutations, 0)

    def test_checkpoint_rejects_changed_postgres_scope(self) -> None:
        """事实集合变化后不得误用旧 checkpoint。"""
        harness = MigrationHarness(FakeSourceStore(_records()))
        run_migration(
            plans=self.plans,
            store_factory=harness.pair,
            options=self._options(),
        )
        changed_rows = _rows()
        changed_rows[0]["content"] = "changed"
        changed_plans = build_migration_file_plans(changed_rows)

        with self.assertRaises(MigrationValidationError) as context:
            run_migration(
                plans=changed_plans,
                store_factory=harness.pair,
                options=self._options(),
            )

        self.assertEqual(context.exception.code, "checkpoint_scope_mismatch")

    def test_source_validation_rejects_postgres_version_drift(self) -> None:
        """文件版本与 chunk 版本漂移必须进入重新向量化路径。"""
        rows = _rows()
        rows[0]["file_index_version"] = 3
        plan = build_migration_file_plans(rows)[0]

        with self.assertRaises(MigrationValidationError) as context:
            validate_source_records(plan, _records())

        self.assertEqual(context.exception.code, "postgres_index_version_mismatch")

    def test_real_import_requires_maintenance_and_verified_backup_manifest(self) -> None:
        """CLI 在连接数据库前强制维护窗口与四类备份证据。"""
        args = argparse.Namespace(
            dry_run=False,
            rollback_check=False,
            batch_size=256,
            sleep_seconds=0,
            sample_top_k=5,
            maintenance_window_confirmed=False,
            backup_manifest=None,
        )
        with self.assertRaises(MigrationValidationError) as context:
            _validate_args(args)
        self.assertEqual(context.exception.code, "maintenance_window_not_confirmed")

        manifest_path = self.root / "backup.json"
        manifest_path.write_text(json.dumps({
            "version": 1,
            "verified": True,
            "created_at": "2026-08-09T00:00:00Z",
            "artifacts": {
                name: {"location": f"backup://{name}", "verified": True}
                for name in ("postgres", "uploads", "chroma", "milvus")
            },
        }))
        evidence = validate_backup_manifest(manifest_path)
        self.assertEqual(len(evidence["manifest_sha256"]), 64)

    def test_cli_rejects_real_import_until_vector_jobs_are_drained(self) -> None:
        """维护窗口确认不能绕过数据库中的 active-job 门禁。"""
        with (
            patch(
                "app.services.vectors.chroma_to_milvus_migration."
                "validate_backup_manifest",
                return_value={"manifest_sha256": "abc"},
            ),
            patch(
                "app.services.vectors.chroma_to_milvus_migration."
                "list_vector_migration_chunk_rows",
                return_value=_rows(),
            ),
            patch(
                "app.services.vectors.chroma_to_milvus_migration."
                "count_active_vector_index_jobs",
                return_value=1,
            ),
        ):
            exit_code = main([
                "--maintenance-window-confirmed",
                "--backup-manifest",
                str(self.root / "manifest.json"),
            ])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
