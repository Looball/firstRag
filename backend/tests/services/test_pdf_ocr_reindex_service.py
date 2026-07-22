"""PDF 单页与多页 OCR 重新识别 service 回归测试。"""

from contextlib import nullcontext
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.documents.pdf_ocr_reindex_service import (
    PdfOcrReindexConflictError,
    PdfOcrReindexValidationError,
    enqueue_pdf_page_ocr_reindex,
    enqueue_pdf_pages_ocr_reindex,
    retry_pdf_ocr_reindex_job,
)


class PdfOcrReindexServiceTests(unittest.TestCase):
    """验证 OCR 重识别批次的权限后业务状态流转。"""

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
            "app.services.documents.pdf_ocr_reindex_service.list_user_pdf_ocr_page_rows",
            return_value=[{"metadata": {"page_number": 2}}],
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
            "app.services.documents.pdf_ocr_reindex_service.list_user_pdf_ocr_page_rows",
            return_value=[],
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(
                PdfOcrReindexValidationError,
                "不存在或不是 OCR",
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
            "app.services.documents.pdf_ocr_reindex_service.list_user_pdf_ocr_page_rows",
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
            "app.services.documents.pdf_ocr_reindex_service.list_user_pdf_ocr_page_rows",
            return_value=[],
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
        ) as reset:
            with self.assertRaisesRegex(PdfOcrReindexValidationError, "不存在或不是 OCR"):
                enqueue_pdf_page_ocr_reindex(1, file_id, 99)

        reset.assert_not_called()

    def test_enqueues_normalized_multi_page_batch_once(self) -> None:
        """重复乱序页码应规范化后只递增一次版本并创建一个 job。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "original_name": "scan.pdf",
            "status": "indexed",
            "index_version": 8,
        }
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value=file_record,
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.list_user_pdf_ocr_page_rows",
            return_value=[
                {"metadata": {"page_number": 1}},
                {"metadata": {"page_number": 3}},
            ],
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.reset_file_index_state",
            return_value={"id": file_id, "index_version": 9, "status": "pending"},
        ) as reset, patch(
            "app.services.documents.pdf_ocr_reindex_service.enqueue_file_vector_index",
            return_value={"id": "job-batch", "status": "queued"},
        ) as enqueue, patch(
            "app.services.documents.pdf_ocr_reindex_service.invalidate_file_knowledge_base_contexts",
        ):
            result = enqueue_pdf_pages_ocr_reindex(1, file_id, [3, 1, 3])

        self.assertEqual(result["page_numbers"], [1, 3])
        self.assertEqual(result["page_count"], 2)
        reset.assert_called_once_with(1, file_id)
        enqueue.assert_called_once()
        self.assertEqual(
            enqueue.call_args.kwargs["job_options"],
            {
                "trigger": "pdf_pages_ocr_reindex",
                "force_ocr_page_numbers": [1, 3],
            },
        )

    def test_rejects_batch_over_configured_limit(self) -> None:
        """超限批次应在读取文件或修改状态前被拒绝。"""
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.PDF_OCR_REINDEX_MAX_BATCH_PAGES",
            2,
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
        ) as get_file:
            with self.assertRaisesRegex(PdfOcrReindexValidationError, "上限 2 页"):
                enqueue_pdf_pages_ocr_reindex(1, uuid4(), [1, 2, 3])
        get_file.assert_not_called()

    def test_retry_preserves_failed_job_page_options(self) -> None:
        """失败重试只能复制服务端保存的原批次页码和当前版本。"""
        file_id = uuid4()
        failed_job_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "failed",
                "index_version": 6,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_vector_index_job",
            return_value={
                "id": failed_job_id,
                "knowledge_file_id": file_id,
                "index_version": 6,
                "status": "failed",
                "options": {
                    "trigger": "pdf_pages_ocr_reindex",
                    "force_ocr_page_numbers": [4, 2],
                },
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.update_knowledge_file_status",
            return_value=1,
        ) as update_status, patch(
            "app.services.documents.pdf_ocr_reindex_service.enqueue_file_vector_index",
            return_value={"id": "retry-job", "status": "queued"},
        ) as enqueue, patch(
            "app.services.documents.pdf_ocr_reindex_service.invalidate_file_knowledge_base_contexts",
        ):
            result = retry_pdf_ocr_reindex_job(1, file_id, failed_job_id)

        self.assertEqual(result["page_numbers"], [2, 4])
        update_status.assert_called_once_with(
            1,
            file_id,
            "pending",
            expected_index_version=6,
        )
        self.assertEqual(
            enqueue.call_args.kwargs["job_options"],
            {
                "trigger": "pdf_pages_ocr_reindex",
                "force_ocr_page_numbers": [2, 4],
            },
        )

    def test_retry_rejects_non_ocr_or_stale_job(self) -> None:
        """非 OCR job 或过期版本不能改变失败文件状态。"""
        file_id = uuid4()
        failed_job_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "failed",
                "index_version": 7,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_vector_index_job",
            return_value={
                "knowledge_file_id": file_id,
                "index_version": 6,
                "status": "failed",
                "options": {
                    "trigger": "pdf_pages_ocr_reindex",
                    "force_ocr_page_numbers": [1],
                },
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.update_knowledge_file_status",
        ) as update_status:
            with self.assertRaisesRegex(PdfOcrReindexConflictError, "版本已过期"):
                retry_pdf_ocr_reindex_job(1, file_id, failed_job_id)
        update_status.assert_not_called()

    def test_retry_rejects_unrelated_vector_job(self) -> None:
        """普通向量化失败 job 不能伪装成 OCR 批次重试。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_reindex_service.file_index_lock",
            return_value=nullcontext(),
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "failed",
                "index_version": 2,
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.get_user_vector_index_job",
            return_value={
                "knowledge_file_id": file_id,
                "index_version": 2,
                "status": "failed",
                "options": {"trigger": "manual_vector_index"},
            },
        ), patch(
            "app.services.documents.pdf_ocr_reindex_service.update_knowledge_file_status",
        ) as update_status:
            with self.assertRaisesRegex(PdfOcrReindexValidationError, "不是可重试"):
                retry_pdf_ocr_reindex_job(1, file_id, uuid4())
        update_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
