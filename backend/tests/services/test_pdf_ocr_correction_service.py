"""PDF OCR 人工修订 service 回归测试。"""

from contextlib import nullcontext
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.documents.pdf_ocr_correction_service import (
    PdfOcrCorrectionValidationError,
    delete_pdf_ocr_page_correction,
    merge_overlapping_chunk_contents,
    save_pdf_ocr_page_correction,
)


class PdfOcrCorrectionServiceTests(unittest.TestCase):
    """验证页级修订合并、版本递增和异步任务语义。"""

    def test_merge_overlapping_chunk_contents_removes_splitter_overlap(self) -> None:
        """完整页面编辑文本不应重复包含 chunk overlap。"""
        merged = merge_overlapping_chunk_contents([
            {"content": "第一段 ABCDEF"},
            {"content": "CDEF 第二段"},
            {"content": "第三段"},
        ])

        self.assertEqual(merged, "第一段 ABCDEF 第二段\n\n第三段")

    def test_save_correction_persists_text_and_enqueues_new_version(self) -> None:
        """保存修订应记录原文、递增版本并提交受控任务。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "original_name": "scan.pdf",
            "status": "indexed",
            "index_version": 4,
        }
        page_chunks = [{
            "content": "OCR ORIGINAL",
            "metadata": {
                "pdf_parse_method": "ocr",
                "ocr_confidence": 42.5,
                "ocr_quality": "low",
            },
        }]
        correction = {
            "original_ocr_text": "OCR ORIGINAL",
            "corrected_text": "HUMAN CORRECTED",
            "revision": 1,
            "updated_at": "2026-07-21T12:00:00+08:00",
        }
        with patch(
            "app.services.documents.pdf_ocr_correction_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_knowledge_file",
            return_value=file_record,
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_pdf_page_chunks",
            return_value=page_chunks,
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_pdf_ocr_correction",
            return_value=None,
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.upsert_pdf_ocr_correction",
            return_value=correction,
        ) as upsert, patch(
            "app.services.documents.pdf_ocr_correction_service.reset_file_index_state",
            return_value={"id": file_id, "index_version": 5, "status": "pending"},
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.enqueue_file_vector_index",
            return_value={"id": "job-1", "status": "queued"},
        ) as enqueue, patch(
            "app.services.documents.pdf_ocr_correction_service.invalidate_file_knowledge_base_contexts",
        ):
            result = save_pdf_ocr_page_correction(
                1,
                file_id,
                2,
                "  HUMAN CORRECTED  ",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["previous_index_version"], 4)
        self.assertEqual(result["index_version"], 5)
        self.assertTrue(result["has_correction"])
        upsert.assert_called_once_with(
            user_id=1,
            knowledge_file_id=file_id,
            page_number=2,
            original_ocr_text="OCR ORIGINAL",
            corrected_text="HUMAN CORRECTED",
        )
        self.assertEqual(
            enqueue.call_args.kwargs["job_options"],
            {
                "trigger": "pdf_page_ocr_correction_saved",
                "corrected_page_numbers": [2],
            },
        )

    def test_save_rejects_unchanged_text_without_reset(self) -> None:
        """没有实际变化的修订不应递增索引版本。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_correction_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_pdf_page_chunks",
            return_value=[{
                "content": "SAME TEXT",
                "metadata": {"pdf_parse_method": "ocr"},
            }],
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_pdf_ocr_correction",
            return_value=None,
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(PdfOcrCorrectionValidationError, "没有变化"):
                save_pdf_ocr_page_correction(1, file_id, 1, "SAME TEXT")

        reset.assert_not_called()

    def test_delete_correction_enqueues_restore_job(self) -> None:
        """撤销修订应删除记录并提交恢复 OCR 的新版本任务。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_correction_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 2,
            },
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_user_pdf_page_chunks",
            return_value=[{
                "content": "HUMAN CORRECTED",
                "metadata": {"pdf_parse_method": "ocr"},
            }],
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.get_pdf_ocr_correction",
            return_value={"revision": 2},
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.delete_pdf_ocr_correction",
            return_value=1,
        ) as delete, patch(
            "app.services.documents.pdf_ocr_correction_service.reset_file_index_state",
            return_value={"id": file_id, "index_version": 3, "status": "pending"},
        ), patch(
            "app.services.documents.pdf_ocr_correction_service.enqueue_file_vector_index",
            return_value={"id": "job-2", "status": "queued"},
        ) as enqueue, patch(
            "app.services.documents.pdf_ocr_correction_service.invalidate_file_knowledge_base_contexts",
        ):
            result = delete_pdf_ocr_page_correction(1, file_id, 2)

        self.assertEqual(result["index_version"], 3)
        self.assertFalse(result["has_correction"])
        delete.assert_called_once_with(1, file_id, 2)
        self.assertEqual(
            enqueue.call_args.kwargs["job_options"]["trigger"],
            "pdf_page_ocr_correction_deleted",
        )


if __name__ == "__main__":
    unittest.main()
