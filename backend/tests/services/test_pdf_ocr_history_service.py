"""PDF OCR 识别历史 service 回归测试。"""

from datetime import UTC, datetime
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.documents.pdf_ocr_history_service import (
    PdfOcrHistoryValidationError,
    get_pdf_ocr_page_history_report,
)


class PdfOcrHistoryServiceTests(unittest.TestCase):
    """验证相邻趋势、文本变化、空历史和权限边界。"""

    def test_report_builds_confidence_and_text_deltas(self) -> None:
        """最新记录应与前一次识别计算置信度和文本变化。"""
        file_id = uuid4()
        latest_id = uuid4()
        previous_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_history_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 3,
            },
        ), patch(
            "app.services.documents.pdf_ocr_history_service.get_user_pdf_page_ocr_metadata",
            return_value={"chunk_index": 0, "metadata": {"page_number": 2}},
        ), patch(
            "app.services.documents.pdf_ocr_history_service.list_pdf_ocr_page_history",
            return_value=[
                {
                    "id": latest_id,
                    "index_version": 3,
                    "ocr_attempt": 3,
                    "source_job_id": uuid4(),
                    "trigger": "pdf_pages_ocr_reindex",
                    "ocr_engine": "tesseract",
                    "ocr_confidence": 82.5,
                    "ocr_quality": "good",
                    "ocr_word_count": 12,
                    "ocr_text": "NEW OCR TEXT",
                    "ocr_text_sha256": "b" * 64,
                    "ocr_text_source": "tesseract",
                    "correction_revision": None,
                    "ocr_strategy": "rotate_90_gray",
                    "ocr_preprocessing": "grayscale",
                    "ocr_psm": 6,
                    "ocr_rotation": 90,
                    "ocr_candidate_count": 2,
                    "ocr_candidate_results": [{
                        "strategy": "rotate_90_gray",
                        "preprocessing": "grayscale",
                        "psm": 6,
                        "rotation": 90,
                        "status": "succeeded",
                        "confidence": 82.5,
                        "word_count": 12,
                        "effective_characters": 10,
                        "text_sha256": "b" * 64,
                        "selected": True,
                    }],
                    "created_at": datetime(2026, 7, 22, 3, 0, tzinfo=UTC),
                },
                {
                    "id": previous_id,
                    "index_version": 2,
                    "ocr_attempt": 2,
                    "source_job_id": uuid4(),
                    "trigger": "pdf_page_ocr_reindex",
                    "ocr_engine": "tesseract",
                    "ocr_confidence": 70.0,
                    "ocr_quality": "good",
                    "ocr_word_count": 10,
                    "ocr_text": "OLD OCR TEXT",
                    "ocr_text_sha256": "a" * 64,
                    "ocr_text_source": "tesseract",
                    "correction_revision": None,
                    "created_at": datetime(2026, 7, 22, 2, 0, tzinfo=UTC),
                },
            ],
        ):
            report = get_pdf_ocr_page_history_report(7, file_id, 2)

        self.assertEqual(report["summary"]["run_count"], 2)
        self.assertEqual(report["summary"]["latest_delta"], 12.5)
        self.assertEqual(report["summary"]["best_confidence"], 82.5)
        self.assertEqual(report["summary"]["improved_count"], 1)
        self.assertEqual(report["runs"][0]["previous_run_id"], str(previous_id))
        self.assertEqual(report["runs"][0]["word_count_delta"], 2)
        self.assertTrue(report["runs"][0]["text_changed"])
        self.assertEqual(report["runs"][0]["ocr_strategy"], "rotate_90_gray")
        self.assertEqual(report["runs"][0]["ocr_rotation"], 90)
        self.assertTrue(
            report["runs"][0]["ocr_candidate_results"][0]["selected"],
        )

    def test_report_returns_empty_history_for_valid_ocr_page(self) -> None:
        """迁移前尚无历史时应返回可理解空清单。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_history_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_history_service.get_user_pdf_page_ocr_metadata",
            return_value={"chunk_index": 0, "metadata": {"page_number": 1}},
        ), patch(
            "app.services.documents.pdf_ocr_history_service.list_pdf_ocr_page_history",
            return_value=[],
        ):
            report = get_pdf_ocr_page_history_report(7, file_id, 1)

        self.assertEqual(report["runs"], [])
        self.assertEqual(report["summary"]["run_count"], 0)
        self.assertIsNone(report["summary"]["latest_delta"])

    def test_report_rejects_non_ocr_page(self) -> None:
        """原生文本页不能伪装为 OCR 历史页面。"""
        file_id = uuid4()
        with patch(
            "app.services.documents.pdf_ocr_history_service.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "original_name": "scan.pdf",
                "status": "indexed",
                "index_version": 1,
            },
        ), patch(
            "app.services.documents.pdf_ocr_history_service.get_user_pdf_page_ocr_metadata",
            return_value=None,
        ):
            with self.assertRaisesRegex(
                PdfOcrHistoryValidationError,
                "不是 OCR 页面",
            ):
                get_pdf_ocr_page_history_report(7, file_id, 3)


if __name__ == "__main__":
    unittest.main()
