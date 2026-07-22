"""引用原文预览与原始文件访问接口回归测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app
from app.repositories.knowledge_chunk_repository import (
    get_user_knowledge_file_chunk_context,
)


class KnowledgeChunkContextRepositoryTests(unittest.TestCase):
    """验证 chunk 上下文查询的权限和版本条件。"""

    def test_context_query_uses_user_file_and_requested_index_version(self) -> None:
        """查询必须绑定 user、file、chunk 和指定 index_version。"""
        file_id = uuid4()
        with patch(
            "app.repositories.knowledge_chunk_repository.fetch_all",
            return_value=[],
        ) as fetch_all:
            result = get_user_knowledge_file_chunk_context(
                user_id=7,
                file_id=file_id,
                chunk_index=4,
                radius=2,
                index_version=5,
            )

        self.assertEqual(result, [])
        sql, params = fetch_all.call_args.args
        self.assertIn("chunk.index_version = %s", sql)
        self.assertIn("%s::integer IS NULL", sql)
        self.assertIn("ORDER BY chunk.index_version DESC", sql)
        self.assertIn("context.user_id = %s", sql)
        self.assertEqual(params, (7, str(file_id), 4, 5, 5, 7, 2, 2))


class SourcePreviewApiTests(unittest.TestCase):
    """验证引用 chunk 预览和原始文件 API。"""

    def setUp(self) -> None:
        """注入固定用户并创建测试客户端。"""
        app.dependency_overrides[get_current_user_id] = lambda: 7
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理认证覆盖和测试客户端。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_chunk_preview_returns_target_neighbors_and_safe_location(self) -> None:
        """预览应高亮目标 chunk，且只返回白名单位置元数据。"""
        file_id = uuid4()
        rows = [
            {
                "original_name": "guide.md",
                "mime_type": "text/markdown",
                "index_version": 3,
                "target_chunk_index": 2,
                "chunk_index": 1,
                "content": "previous",
                "metadata": {"h1": "指南", "source": "/app/uploads/secret"},
            },
            {
                "original_name": "guide.md",
                "mime_type": "text/markdown",
                "index_version": 3,
                "target_chunk_index": 2,
                "chunk_index": 2,
                "content": "target",
                "metadata": {
                    "h1": "指南",
                    "h2": "安装",
                    "location_type": "pdf_page",
                    "page_index": 1,
                    "page_number": 2,
                    "page_count": 3,
                    "paragraph_start": 4,
                    "paragraph_end": 5,
                    "pdf_parse_method": "ocr",
                    "ocr_engine": "tesseract",
                    "ocr_languages": "chi_sim+eng",
                    "ocr_dpi": 300,
                    "ocr_confidence": 62.4,
                    "ocr_quality": "low",
                    "ocr_word_count": 8,
                    "ocr_attempt": 2,
                    "ocr_text_source": "manual_correction",
                    "ocr_correction_applied": True,
                    "ocr_correction_revision": 3,
                    "ocr_correction_character_count": 18,
                    "ocr_correction_updated_at": "2026-07-21T12:00:00+08:00",
                },
            },
        ]
        with patch(
            "app.api.knowledge_files.get_user_knowledge_file_chunk_context",
            return_value=rows,
        ) as get_context:
            response = self.client.get(
                f"/chat/knowledge-files/{file_id}/chunks/2?radius=1",
            )

        self.assertEqual(response.status_code, 200)
        get_context.assert_called_once_with(
            user_id=7,
            file_id=file_id,
            chunk_index=2,
            radius=1,
            index_version=None,
        )
        payload = response.json()
        self.assertEqual(payload["target_chunk_index"], 2)
        self.assertFalse(payload["chunks"][0]["is_target"])
        self.assertTrue(payload["chunks"][1]["is_target"])
        self.assertEqual(payload["chunks"][1]["location"]["h2"], "安装")
        self.assertEqual(payload["chunks"][1]["location"]["page_number"], 2)
        self.assertEqual(payload["chunks"][1]["location"]["page_index"], 1)
        self.assertEqual(payload["chunks"][1]["location"]["page_count"], 3)
        self.assertEqual(
            payload["chunks"][1]["location"]["paragraph_start"],
            4,
        )
        self.assertEqual(payload["chunks"][1]["location"]["paragraph_end"], 5)
        self.assertEqual(
            payload["chunks"][1]["location"]["pdf_parse_method"],
            "ocr",
        )
        self.assertEqual(
            payload["chunks"][1]["location"]["ocr_engine"],
            "tesseract",
        )
        self.assertEqual(
            payload["chunks"][1]["location"]["ocr_confidence"],
            62.4,
        )
        self.assertEqual(
            payload["chunks"][1]["location"]["ocr_quality"],
            "low",
        )
        self.assertTrue(
            payload["chunks"][1]["location"]["ocr_correction_applied"],
        )
        self.assertEqual(
            payload["chunks"][1]["location"]["ocr_correction_revision"],
            3,
        )
        self.assertNotIn("source", payload["chunks"][0]["location"])

    def test_chunk_preview_hides_missing_or_cross_user_resource(self) -> None:
        """不存在或跨用户 chunk 统一返回 404。"""
        file_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_file_chunk_context",
            return_value=[],
        ):
            response = self.client.get(
                f"/chat/knowledge-files/{file_id}/chunks/9",
            )

        self.assertEqual(response.status_code, 404)

    def test_original_file_content_is_returned_inline(self) -> None:
        """属于当前用户且位于 uploads 内的文件应以内联响应返回。"""
        file_id = uuid4()
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "guide.txt"
            storage_path.write_text("original content", encoding="utf-8")
            with patch(
            "app.api.knowledge_files.get_user_knowledge_file",
            return_value={
                "storage_path": str(storage_path),
                "mime_type": "text/html",
                "original_name": "指南.txt",
                },
            ), patch(
                "app.api.knowledge_files.resolve_knowledge_file_storage_path",
                return_value=storage_path,
            ):
                response = self.client.get(
                    f"/chat/knowledge-files/{file_id}/content",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "original content")
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertTrue(
            response.headers["content-disposition"].startswith("inline;"),
        )

    def test_original_file_path_violation_is_hidden(self) -> None:
        """数据库路径越界时不得读取磁盘文件。"""
        file_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_file",
            return_value={
                "storage_path": "/tmp/outside.txt",
                "mime_type": "text/plain",
                "original_name": "outside.txt",
            },
        ), patch(
            "app.api.knowledge_files.resolve_knowledge_file_storage_path",
            side_effect=ValueError("outside uploads"),
        ):
            response = self.client.get(
                f"/chat/knowledge-files/{file_id}/content",
            )

        self.assertEqual(response.status_code, 404)

    def test_pdf_page_preview_returns_private_png(self) -> None:
        """当前用户的 PDF 目标页应以内联 PNG 返回。"""
        file_id = uuid4()
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "scan.pdf"
            storage_path.write_bytes(b"%PDF-test")
            with patch(
                "app.api.knowledge_files.get_user_knowledge_file",
                return_value={
                    "storage_path": str(storage_path),
                    "original_name": "scan.pdf",
                },
            ), patch(
                "app.api.knowledge_files.resolve_knowledge_file_storage_path",
                return_value=storage_path,
            ), patch(
                "app.api.knowledge_files.render_pdf_page_preview",
                return_value=b"\x89PNG\r\n\x1a\npreview",
            ) as render_preview:
                response = self.client.get(
                    f"/chat/knowledge-files/{file_id}/pages/2/preview",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["cache-control"], "private, max-age=60")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertTrue(response.content.startswith(b"\x89PNG"))
        render_preview.assert_called_once_with(storage_path, 2)

    def test_pdf_page_preview_hides_cross_user_file(self) -> None:
        """跨用户或不存在的 PDF 不得进入磁盘渲染流程。"""
        file_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_file",
            return_value=None,
        ), patch(
            "app.api.knowledge_files.render_pdf_page_preview",
        ) as render_preview:
            response = self.client.get(
                f"/chat/knowledge-files/{file_id}/pages/1/preview",
            )

        self.assertEqual(response.status_code, 404)
        render_preview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
