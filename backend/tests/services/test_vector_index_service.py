"""向量索引服务回归测试。"""

from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from langchain_core.documents import Document

from app.services.vectors.vector_index_service import (
    audit_postgres_chunk_identity,
    build_pdf_ocr_history_entries,
    compensate_failed_file_index,
    index_file_vectors,
    index_knowledge_file_record,
)
from app.services.vectors.embedding_settings_service import EmbeddingModelSettings
from app.services.vectors import vector_store_factory
from app.services.vectors.milvus_vector_store import MilvusVectorStore


class VectorIndexServiceTests(unittest.TestCase):
    """验证文件记录字段能够正确传入文档解析层。"""

    def test_compensation_deletes_only_current_vector_identity(self) -> None:
        """失败补偿应保留独立 dense-only rollback collection。"""
        vector_store = Mock()
        with patch(
            "app.services.vectors.vector_index_service.delete_file_chunks",
        ) as delete_chunks:
            compensate_failed_file_index(7, "file-a", vector_store)

        vector_store.delete_current_file_vectors.assert_called_once_with(
            user_id=7,
            file_id="file-a",
        )
        vector_store.delete_file_vectors.assert_not_called()
        delete_chunks.assert_called_once_with(7, "file-a")

    def test_compensation_cleanup_adapter_scans_all_identities(self) -> None:
        """无法恢复当前 identity 时，credential-free cleanup 应避免残留。"""
        cleanup_store = Mock()
        cleanup_store.collection_name = ""
        with patch(
            "app.services.vectors.vector_index_service.get_vector_store",
            side_effect=ValueError("missing settings"),
        ), patch(
            "app.services.vectors.vector_index_service.get_vector_store_for_cleanup",
            return_value=cleanup_store,
        ), patch(
            "app.services.vectors.vector_index_service.delete_file_chunks",
        ):
            compensate_failed_file_index(7, "file-a")

        cleanup_store.delete_file_vectors.assert_called_once_with(
            user_id=7,
            file_id="file-a",
        )
        cleanup_store.delete_current_file_vectors.assert_not_called()

    def test_index_file_vectors_forwards_original_file_name(self) -> None:
        """索引时应使用用户上传文件名，而不是引用未定义的文件记录。"""
        file_id = uuid4()
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "stored-file"
            storage_path.write_text("测试内容", encoding="utf-8")

            with patch(
                "app.services.vectors.vector_index_service.load_document",
                side_effect=RuntimeError("stop-after-loader"),
            ) as load_document:
                with self.assertRaisesRegex(RuntimeError, "stop-after-loader"):
                    index_file_vectors(
                        user_id=1,
                        file_id=file_id,
                        storage_path=storage_path,
                        index_version=0,
                        original_name="用户上传文件.txt",
                    )

        load_document.assert_called_once_with(
            file_path=storage_path,
            file_id=file_id,
            user_id=1,
            original_name="用户上传文件.txt",
            force_ocr_page_numbers=None,
            pdf_ocr_corrections=None,
            previous_ocr_attempts=None,
        )

    def test_build_history_uses_raw_ocr_text_and_strips_internal_metadata(
        self,
    ) -> None:
        """历史应保存 Tesseract 原文，且内部字段不能进入后续 chunks。"""
        document = Document(
            page_content="HUMAN CORRECTED",
            metadata={
                "pdf_parse_method": "ocr",
                "page_number": 2,
                "ocr_attempt": 4,
                "ocr_engine": "tesseract",
                "ocr_confidence": 81.25,
                "ocr_quality": "good",
                "ocr_word_count": 7,
                "ocr_text_source": "manual_correction",
                "ocr_correction_revision": 3,
                "ocr_strategy": "single_block_binary",
                "ocr_preprocessing": "binary",
                "ocr_psm": 6,
                "ocr_rotation": 0,
                "ocr_candidate_count": 2,
                "_ocr_history_text": "RAW TESSERACT OCR",
                "_ocr_history_candidates": [{
                    "strategy": "single_block_binary",
                    "preprocessing": "binary",
                    "psm": 6,
                    "rotation": 0,
                    "status": "succeeded",
                    "confidence": 81.25,
                    "word_count": 7,
                    "effective_characters": 15,
                    "text_sha256": "c" * 64,
                    "selected": True,
                }],
            },
        )

        entries = build_pdf_ocr_history_entries(
            [document],
            index_version=5,
            source_job_id="00000000-0000-0000-0000-000000000001",
            trigger="pdf_page_ocr_correction_saved",
        )

        self.assertEqual(entries[0]["ocr_text"], "RAW TESSERACT OCR")
        self.assertEqual(entries[0]["ocr_attempt"], 4)
        self.assertEqual(entries[0]["correction_revision"], 3)
        self.assertEqual(entries[0]["ocr_strategy"], "single_block_binary")
        self.assertEqual(entries[0]["ocr_candidate_count"], 1)
        self.assertTrue(entries[0]["ocr_candidate_results"][0]["selected"])
        self.assertNotIn("_ocr_history_text", document.metadata)
        self.assertNotIn("_ocr_history_candidates", document.metadata)

    def test_postgres_chunk_audit_rejects_id_or_version_drift(self) -> None:
        """双存储审计应拒绝 chunk ID 集合或 index_version 漂移。"""
        file_id = uuid4()
        with patch(
            "app.services.vectors.vector_index_service.list_file_chunk_identity_rows",
            return_value=[
                {
                    "chunk_id": "chunk-a",
                    "parent_id": "parent-a",
                    "child_index": 0,
                    "index_version": 4,
                },
                {
                    "chunk_id": "chunk-b",
                    "parent_id": "parent-a",
                    "child_index": 1,
                    "index_version": 4,
                },
            ],
        ), patch(
            "app.services.vectors.vector_index_service.list_file_parent_identity_rows",
            return_value=[{"parent_id": "parent-a", "index_version": 4}],
        ):
            audit_postgres_chunk_identity(
                user_id=1,
                file_id=file_id,
                expected_chunk_ids=["chunk-b", "chunk-a"],
                expected_parent_ids=["parent-a"],
                expected_index_version=4,
            )

        for rows in (
            [{
                "chunk_id": "chunk-a",
                "parent_id": "parent-a",
                "child_index": 0,
                "index_version": 4,
            }],
            [
                {
                    "chunk_id": "chunk-a",
                    "parent_id": "parent-a",
                    "child_index": 0,
                    "index_version": 3,
                },
                {
                    "chunk_id": "chunk-b",
                    "parent_id": "parent-a",
                    "child_index": 1,
                    "index_version": 3,
                },
            ],
        ):
            with self.subTest(rows=rows), patch(
                "app.services.vectors.vector_index_service.list_file_chunk_identity_rows",
                return_value=rows,
            ), patch(
                "app.services.vectors.vector_index_service.list_file_parent_identity_rows",
                return_value=[{"parent_id": "parent-a", "index_version": 4}],
            ):
                with self.assertRaisesRegex(RuntimeError, "parent/child 审计失败"):
                    audit_postgres_chunk_identity(
                        user_id=1,
                        file_id=file_id,
                        expected_chunk_ids=["chunk-a", "chunk-b"],
                        expected_parent_ids=["parent-a"],
                        expected_index_version=4,
                    )

    def test_index_file_vectors_persists_parent_child_hierarchy(self) -> None:
        """索引应同时写入 parent 正文与带稳定 identity 的 child。"""
        file_id = uuid4()
        vector_store = Mock()
        vector_store.ensure_collection.return_value = "collection"
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "document.md"
            storage_path.write_text("placeholder", encoding="utf-8")
            loaded = Document(
                page_content="# 第一章\n\n" + "企业制度内容。" * 120,
                metadata={
                    "user_id": "1",
                    "file_id": str(file_id),
                    "file_name": "document.md",
                    "file_type": "md",
                    "content_format": "markdown",
                },
            )
            with patch(
                "app.services.vectors.vector_index_service.load_document",
                return_value=[loaded],
            ), patch(
                "app.services.vectors.vector_index_service.get_vector_store",
                return_value=vector_store,
            ), patch(
                "app.services.vectors.vector_index_service.replace_file_chunks",
            ) as replace_chunks, patch(
                "app.services.vectors.vector_index_service.audit_postgres_chunk_identity",
            ) as audit_identity, patch(
                "app.services.vectors.vector_index_service.record_pdf_ocr_history_entries",
            ):
                result = index_file_vectors(
                    user_id=1,
                    file_id=file_id,
                    storage_path=storage_path,
                    index_version=4,
                    original_name="document.md",
                )

        self.assertEqual(result["parent_count"], 1)
        self.assertGreater(result["chunk_count"], 1)
        replace_kwargs = replace_chunks.call_args.kwargs
        self.assertEqual(len(replace_kwargs["parents"]), 1)
        self.assertEqual(
            replace_kwargs["parent_ids"],
            [f"1:{file_id}:v4:p0"],
        )
        self.assertTrue(all(
            chunk.metadata["parent_id"] == f"1:{file_id}:v4:p0"
            for chunk in replace_kwargs["chunks"]
        ))
        self.assertEqual(
            replace_kwargs["chunk_ids"],
            [
                f"1:{file_id}:v4:p0:c{child_index}"
                for child_index in range(result["chunk_count"])
            ],
        )
        audit_identity.assert_called_once_with(
            user_id=1,
            file_id=file_id,
            expected_chunk_ids=replace_kwargs["chunk_ids"],
            expected_parent_ids=replace_kwargs["parent_ids"],
            expected_index_version=4,
        )

    def test_index_record_loads_persistent_pdf_ocr_corrections(self) -> None:
        """worker 索引文件时应加载并传递全部持久化页级修订。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "original_name": "scan.pdf",
            "storage_path": "/tmp/scan.pdf",
        }
        with patch(
            "app.services.vectors.vector_index_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.vectors.vector_index_service.update_knowledge_file_status",
            return_value=1,
        ), patch(
            "app.services.vectors.vector_index_service.invalidate_file_knowledge_base_contexts",
        ), patch(
            "app.services.vectors.vector_index_service.list_pdf_ocr_corrections",
            return_value=[{
                "page_number": 2,
                "corrected_text": "HUMAN CORRECTED",
                "revision": 4,
                "updated_at": "2026-07-21T12:00:00+08:00",
            }],
        ), patch(
            "app.services.vectors.vector_index_service.get_latest_pdf_ocr_attempts",
            return_value={2: 3},
        ), patch(
            "app.services.vectors.vector_index_service._backfill_legacy_pdf_ocr_history",
            return_value={2: 3},
        ), patch(
            "app.services.vectors.vector_index_service.index_file_vectors",
            return_value={"chunk_count": 1},
        ) as index_file:
            result = index_knowledge_file_record(
                file_record=file_record,
                user_id=1,
                index_version=3,
            )

        self.assertEqual(result["status"], "indexed")
        self.assertEqual(
            index_file.call_args.kwargs["pdf_ocr_corrections"],
            {
                2: {
                    "page_number": 2,
                    "corrected_text": "HUMAN CORRECTED",
                    "revision": 4,
                    "updated_at": "2026-07-21T12:00:00+08:00",
                },
            },
        )
        self.assertEqual(
            index_file.call_args.kwargs["previous_ocr_attempts"],
            {2: 3},
        )

    def test_factory_builds_milvus_adapter_and_safe_collection_name(self) -> None:
        """Milvus provider 应使用 ADR collection identity 和用户 embedding。"""
        settings = EmbeddingModelSettings(
            provider="qwen",
            model="text-embedding-v4",
            api_key="test-only",
            base_url=None,
            dimensions=1024,
            timeout_seconds=10,
            max_retries=0,
        )
        client = object()
        embedding_model = object()
        with patch.object(
            vector_store_factory,
            "get_effective_embedding_model_settings",
            return_value=settings,
        ), patch.object(
            vector_store_factory,
            "create_embedding_model_from_settings",
            return_value=embedding_model,
        ), patch.object(
            vector_store_factory,
            "_create_milvus_client",
            return_value=client,
        ):
            store = vector_store_factory.get_vector_store(user_id=42)

        self.assertIsInstance(store, MilvusVectorStore)
        self.assertRegex(
            store.collection_name,
            r"^firstrag_u42_[0-9a-f]{12}$",
        )
        self.assertNotIn("-", store.collection_name)
        self.assertIs(store._client, client)
        self.assertIs(store._embedding_model, embedding_model)
        self.assertIsNone(store._sparse_encoder)

    def test_factory_v2_identity_includes_sparse_model_and_revision(self) -> None:
        """启用 T-142 flag 后应创建独立 v2 identity 并绑定 sparse client。"""
        settings = EmbeddingModelSettings(
            provider="qwen",
            model="text-embedding-v4",
            api_key="test-only",
            base_url=None,
            dimensions=1024,
            timeout_seconds=10,
            max_retries=0,
        )
        dense_only_name = vector_store_factory.build_milvus_user_collection_name(
            "firstrag",
            42,
            settings,
        )
        with patch.object(
            vector_store_factory,
            "MILVUS_DENSE_SPARSE_WRITE_ENABLED",
            True,
        ), patch.object(
            vector_store_factory,
            "get_effective_embedding_model_settings",
            return_value=settings,
        ), patch.object(
            vector_store_factory,
            "create_embedding_model_from_settings",
            return_value=object(),
        ), patch.object(
            vector_store_factory,
            "_create_milvus_client",
            return_value=object(),
        ):
            store = vector_store_factory.get_vector_store(user_id=42)

        expected_name = vector_store_factory.build_milvus_user_collection_name(
            "firstrag",
            42,
            settings,
            sparse_model=vector_store_factory.SPARSE_ENCODER_MODEL,
            sparse_revision=vector_store_factory.SPARSE_ENCODER_REVISION,
        )
        self.assertEqual(store.collection_name, expected_name)
        self.assertNotEqual(store.collection_name, dense_only_name)
        self.assertIsNotNone(store._sparse_encoder)

    def test_cleanup_factory_does_not_require_embedding_settings(self) -> None:
        """永久删除在用户凭据缺失时仍应能扫描 Milvus identities。"""
        client = object()
        with patch.object(
            vector_store_factory,
            "_create_milvus_client",
            return_value=client,
        ), patch.object(
            vector_store_factory,
            "get_effective_embedding_model_settings",
        ) as settings:
            store = vector_store_factory.get_vector_store_for_cleanup(7)

        settings.assert_not_called()
        self.assertIsInstance(store, MilvusVectorStore)
        self.assertEqual(store._user_collection_prefix, "firstrag_u7_")

    def test_failed_indexed_publish_runs_cross_store_compensation(self) -> None:
        """最终状态发布失败时不得保留向量和 PostgreSQL chunks。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "original_name": "document.txt",
            "storage_path": "/tmp/document.txt",
        }
        with patch(
            "app.services.vectors.vector_index_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.vectors.vector_index_service.update_knowledge_file_status",
            side_effect=[1, 0],
        ), patch(
            "app.services.vectors.vector_index_service.invalidate_file_knowledge_base_contexts",
        ), patch(
            "app.services.vectors.vector_index_service.list_pdf_ocr_corrections",
            return_value=[],
        ), patch(
            "app.services.vectors.vector_index_service.get_latest_pdf_ocr_attempts",
            return_value={},
        ), patch(
            "app.services.vectors.vector_index_service._backfill_legacy_pdf_ocr_history",
            return_value={},
        ), patch(
            "app.services.vectors.vector_index_service.index_file_vectors",
            return_value={"chunk_count": 1},
        ), patch(
            "app.services.vectors.vector_index_service.compensate_failed_file_index",
        ) as compensate:
            with self.assertRaisesRegex(RuntimeError, "版本已过期"):
                index_knowledge_file_record(
                    file_record=file_record,
                    user_id=1,
                    index_version=3,
                )

        compensate.assert_called_once_with(1, file_id)


if __name__ == "__main__":
    unittest.main()
