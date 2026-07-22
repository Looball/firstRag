"""文件级 PDF OCR 质量巡检 service 回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.documents.pdf_ocr_quality_service import (
    PdfOcrQualityConflictError,
    get_pdf_ocr_quality_report,
)


class PdfOcrQualityServiceTests(unittest.TestCase):
    """验证质量统计、排序、摘要截断和文件状态边界。"""

    def test_report_prioritizes_uncorrected_low_confidence_pages(self) -> None:
        """待处理低置信度页应排在已校对页和正常页之前。"""
        file_id = uuid4()
        rows = [
            {
                "chunk_index": 0,
                "index_version": 4,
                "content": "Clear page",
                "metadata": {
                    "page_number": 1,
                    "page_count": 3,
                    "ocr_confidence": 91.2,
                    "ocr_quality": "ok",
                },
            },
            {
                "chunk_index": 1,
                "index_version": 4,
                "content": "Needs review",
                "metadata": {
                    "page_number": 2,
                    "page_count": 3,
                    "ocr_confidence": 38.5,
                    "ocr_quality": "low",
                    "ocr_attempt": 2,
                },
            },
            {
                "chunk_index": 2,
                "index_version": 4,
                "content": "Corrected low confidence page",
                "metadata": {
                    "page_number": 3,
                    "page_count": 3,
                    "ocr_confidence": 42.0,
                    "ocr_quality": "low",
                },
            },
        ]
        with patch(
            "app.services.documents.pdf_ocr_quality_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 4,
            },
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.list_user_pdf_ocr_page_rows",
            return_value=rows,
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.list_pdf_ocr_corrections",
            return_value=[{
                "page_number": 3,
                "revision": 2,
                "updated_at": "2026-07-22T10:00:00+08:00",
            }],
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.get_pdf_ocr_history_summaries",
            return_value={
                2: {
                    "history_count": 2,
                    "latest_confidence": 38.5,
                    "previous_confidence": 31.0,
                },
            },
        ):
            report = get_pdf_ocr_quality_report(7, file_id)

        self.assertIsNotNone(report)
        self.assertEqual(
            [page["page_number"] for page in report["pages"]],
            [2, 3, 1],
        )
        self.assertTrue(report["pages"][0]["needs_review"])
        self.assertEqual(report["pages"][0]["ocr_attempt"], 2)
        self.assertEqual(report["pages"][0]["history_count"], 2)
        self.assertEqual(report["pages"][0]["latest_confidence_delta"], 7.5)
        self.assertTrue(report["pages"][1]["has_correction"])
        self.assertEqual(report["pages"][1]["correction_revision"], 2)
        self.assertEqual(report["summary"]["document_page_count"], 3)
        self.assertEqual(report["summary"]["ocr_page_count"], 3)
        self.assertEqual(report["summary"]["needs_review_count"], 1)
        self.assertEqual(report["summary"]["low_confidence_count"], 2)
        self.assertEqual(report["summary"]["corrected_count"], 1)
        self.assertEqual(report["summary"]["average_confidence"], 57.23)
        self.assertGreaterEqual(report["summary"]["max_reindex_pages"], 1)

    def test_report_returns_empty_pages_for_native_text_pdf(self) -> None:
        """没有 OCR 页面的 PDF 应返回空清单而非错误。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_quality_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "native.pdf",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.list_user_pdf_ocr_page_rows",
            return_value=[],
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.list_pdf_ocr_corrections",
            return_value=[],
        ), patch(
            "app.services.documents.pdf_ocr_quality_service.get_pdf_ocr_history_summaries",
            return_value={},
        ):
            report = get_pdf_ocr_quality_report(7, file_id)

        self.assertEqual(report["pages"], [])
        self.assertEqual(report["summary"]["ocr_page_count"], 0)
        self.assertIsNone(report["summary"]["average_confidence"])

    def test_report_rejects_file_while_indexing(self) -> None:
        """索引未稳定时不能返回可能过期的页级清单。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_quality_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "processing",
                "index_version": 2,
            },
        ):
            with self.assertRaisesRegex(
                PdfOcrQualityConflictError,
                "尚未完成索引",
            ):
                get_pdf_ocr_quality_report(7, file_id)


if __name__ == "__main__":
    unittest.main()
