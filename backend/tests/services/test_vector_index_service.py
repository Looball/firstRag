"""向量索引服务回归测试。"""

from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.documents import Document

from app.services.vectors.vector_index_service import (
    build_pdf_ocr_history_entries,
    get_vector_store,
    index_file_vectors,
    index_knowledge_file_record,
)


class VectorIndexServiceTests(unittest.TestCase):
    """验证文件记录字段能够正确传入文档解析层。"""

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
                "_ocr_history_text": "RAW TESSERACT OCR",
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
        self.assertNotIn("_ocr_history_text", document.metadata)

    def test_get_vector_store_uses_http_client_when_host_is_configured(
        self,
    ) -> None:
        """Compose 配置 Chroma host 后应连接独立 server。"""
        with patch(
            "app.services.vectors.vector_index_service.CHROMA_HOST",
            "chroma",
        ), patch(
            "app.services.vectors.vector_index_service.CHROMA_PORT",
            8000,
        ), patch(
            "app.services.vectors.vector_index_service.CHROMA_SSL",
            False,
        ), patch(
            "app.services.vectors.vector_index_service.Chroma",
        ) as chroma:
            get_vector_store(collection_name="test-collection")

        chroma.assert_called_once_with(
            collection_name="test-collection",
            embedding_function=None,
            host="chroma",
            port=8000,
            ssl=False,
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

    def test_get_vector_store_keeps_embedded_mode_without_host(self) -> None:
        """未配置 Chroma host 时应保留单进程本地持久化模式。"""
        with patch(
            "app.services.vectors.vector_index_service.CHROMA_HOST",
            "",
        ), patch(
            "app.services.vectors.vector_index_service.Chroma",
        ) as chroma:
            get_vector_store(
                persist_directory="/tmp/firstrag-test-chroma",
                collection_name="test-collection",
            )

        chroma.assert_called_once_with(
            collection_name="test-collection",
            embedding_function=None,
            persist_directory="/tmp/firstrag-test-chroma",
        )


if __name__ == "__main__":
    unittest.main()
