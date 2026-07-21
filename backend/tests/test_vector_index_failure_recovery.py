"""向量化失败分类与恢复提示测试。"""

import unittest
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.vectors.vector_index_queue_service import (
    build_safe_vector_index_error_message,
    build_vector_index_failure_hint,
    classify_vector_index_failure,
    serialize_vector_index_job,
)


class VectorIndexFailureRecoveryTests(unittest.TestCase):
    """验证向量化失败类型和前端恢复提示协议。"""

    def test_classify_main_failure_types(self) -> None:
        """常见失败信息应归类为稳定的 failure_type。"""
        cases = {
            "不支持的文件类型：.exe": "unsupported_file_type",
            "文件为空，未解析出可入库的文本分块": "empty_document",
            "图片解析需要支持视觉能力的聊天模型": "image_parse_error",
            "PDF OCR 引擎不可用，请安装 Tesseract": "ocr_error",
            "PDF loader 解析失败": "parse_error",
            "Embedding request returned 429": "embedding_error",
            "Chroma collection write failed": "vector_store_error",
            "knowledge_file_chunks chunk insert failed": "chunk_write_error",
            "psycopg database connection closed": "database_error",
            "vector index task timeout after 600 seconds": "task_timeout",
            "索引任务版本已过期": "stale_job",
        }

        for message, expected_type in cases.items():
            with self.subTest(message=message):
                self.assertEqual(
                    classify_vector_index_failure(message),
                    expected_type,
                )

    def test_failure_hints_cover_recovery_actions(self) -> None:
        """每类失败都应给出面向恢复的提示。"""
        for failure_type in [
            "parse_error",
            "unsupported_file_type",
            "empty_document",
            "image_parse_error",
            "ocr_error",
            "embedding_error",
            "vector_store_error",
            "chunk_write_error",
            "database_error",
            "task_timeout",
            "stale_job",
            "unknown_error",
        ]:
            with self.subTest(failure_type=failure_type):
                hint = build_vector_index_failure_hint(failure_type)
                self.assertIsInstance(hint, str)
                self.assertTrue(hint)

    def test_serialize_failed_job_keeps_retry_contract(self) -> None:
        """失败任务响应应稳定返回 failure_type、failure_hint 和 can_retry。"""
        serialized = serialize_vector_index_job({
            "id": "job-1",
            "user_id": 1,
            "knowledge_file_id": "file-1",
            "knowledge_base_id": None,
            "index_version": 1,
            "status": "failed",
            "attempts": 3,
            "max_attempts": 3,
            "error_message": "knowledge_file_chunks chunk insert failed",
            "result": None,
            "created_at": "2026-06-28T08:00:00",
            "updated_at": "2026-06-28T08:01:00",
        })

        self.assertEqual(serialized["failure_type"], "chunk_write_error")
        self.assertEqual(serialized["error_message"], "全文分块写入失败")
        self.assertIn("全文分块写入失败", serialized["failure_hint"])
        self.assertTrue(serialized["can_retry"])

    def test_safe_error_message_does_not_expose_sensitive_detail(self) -> None:
        """面向前端的错误摘要不应暴露路径、连接串或 API Key。"""
        raw_error = (
            "Embedding request failed at /srv/firstrag/vector_db "
            "with api_key=sk-secret"
        )

        failure_type = classify_vector_index_failure(raw_error)
        safe_message = build_safe_vector_index_error_message(
            raw_error,
            failure_type,
        )

        self.assertEqual(failure_type, "embedding_error")
        self.assertEqual(safe_message, "Embedding 调用失败")
        self.assertNotIn("/srv", safe_message or "")
        self.assertNotIn("sk-secret", safe_message or "")


if __name__ == "__main__":
    unittest.main()
