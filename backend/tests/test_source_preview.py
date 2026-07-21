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


if __name__ == "__main__":
    unittest.main()
