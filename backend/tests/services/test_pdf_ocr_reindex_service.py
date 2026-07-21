"""PDF 单页 OCR 重新识别 service 回归测试。"""

from contextlib import nullcontext
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.documents.pdf_ocr_reindex_service import (
    PdfOcrReindexConflictError,
    PdfOcrReindexValidationError,
    enqueue_pdf_page_ocr_reindex,
)


class PdfOcrReindexServiceTests(unittest.TestCase):
    """验证单页 OCR 重识别的权限后业务状态流转。"""

    def test_enqueues_new_index_version_with_forced_page(self) -> None:
        """OCR 页应递增版本并把受限强制页选项写入任务。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "original_name": "scan.pdf",
            "status": "indexed",
            "index_version": 3,
        }
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value=file_record,
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_pdf_page_ocr_metadata",
            return_value={"metadata": {"pdf_parse_method": "ocr"}},
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
            return_value={"id": file_id, "index_version": 4, "status": "pending"},
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.enqueue_file_vector_index",
            return_value={"id": "job-1", "status": "queued"},
        ) as enqueue, patch(
            "app.services.documents.pdf_ocr_reindex_service.invalidate_file_knowledge_base_contexts",
        ):
            result = enqueue_pdf_page_ocr_reindex(1, file_id, 2)

        self.assertIsNotNone(result)
        self.assertEqual(result["previous_index_version"], 3)
        self.assertEqual(result["index_version"], 4)
        enqueue.assert_called_once()
        self.assertEqual(
            enqueue.call_args.kwargs["job_options"],
            {
                "trigger": "pdf_page_ocr_reindex",
                "force_ocr_page_numbers": [2],
            },
        )

    def test_rejects_native_text_page_without_resetting_version(self) -> None:
        """原生文本页不应创建 OCR 重识别任务或改变索引版本。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "native.pdf",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_pdf_page_ocr_metadata",
            return_value={"metadata": {"pdf_parse_method": "native_text"}},
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(
                PdfOcrReindexValidationError,
                "不需要 OCR",
            ):
                enqueue_pdf_page_ocr_reindex(1, file_id, 1)

        reset.assert_not_called()

    def test_rejects_non_pdf_without_resetting_version(self) -> None:
        """非 PDF 文件不应进入页面 metadata 查询或修改索引状态。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "notes.txt",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_pdf_page_ocr_metadata",
        ) as get_page, patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(PdfOcrReindexValidationError, "只有 PDF"):
                enqueue_pdf_page_ocr_reindex(1, file_id, 1)

        get_page.assert_not_called()
        reset.assert_not_called()

    def test_rejects_busy_file_without_resetting_version(self) -> None:
        """活跃索引中的文件应返回冲突并保留当前版本。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexing",
                "index_version": 2,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(PdfOcrReindexConflictError, "等待当前任务"):
                enqueue_pdf_page_ocr_reindex(1, file_id, 1)

        reset.assert_not_called()

    def test_rejects_missing_page_without_resetting_version(self) -> None:
        """不存在或未索引的页码不应递增文件版本。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 2,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_pdf_page_ocr_metadata",
            return_value=None,
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(PdfOcrReindexValidationError, "页面不存在"):
                enqueue_pdf_page_ocr_reindex(1, file_id, 99)

        reset.assert_not_called()


if __name__ == "__main__":
    unittest.main()
