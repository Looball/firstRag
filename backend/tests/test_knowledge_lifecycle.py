"""知识库与知识文件生命周期接口回归测试。"""

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app
from app.repositories.knowledge_file_repository import (
    purge_user_knowledge_file_records,
)
from app.services.knowledge_file_lifecycle_service import (
    permanently_delete_knowledge_file,
)


class KnowledgeBaseLifecycleApiTests(unittest.TestCase):
    """验证知识库重命名、回收站和恢复接口。"""

    def setUp(self) -> None:
        """注入固定用户并创建测试客户端。"""
        app.dependency_overrides[get_current_user_id] = lambda: 7
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理认证覆盖和测试客户端。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_list_deleted_knowledge_bases(self) -> None:
        """回收站列表应返回文件和会话数量。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_user_deleted_knowledge_bases",
            return_value=[{
                "id": knowledge_base_id,
                "name": "归档资料",
                "is_default": False,
                "file_count": 2,
                "conversation_count": 3,
                "created_at": "2026-07-01T00:00:00+08:00",
                "updated_at": "2026-07-21T00:00:00+08:00",
                "deleted_at": "2026-07-21T00:00:00+08:00",
            }],
        ):
            response = self.client.get("/chat/knowledge-bases/trash")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["knowledge_bases"][0]["id"],
            str(knowledge_base_id),
        )
        self.assertEqual(response.json()["knowledge_bases"][0]["file_count"], 2)
        self.assertEqual(
            response.json()["knowledge_bases"][0]["conversation_count"],
            3,
        )

    def test_rename_knowledge_base_trims_name(self) -> None:
        """重命名应保存去除首尾空格后的名称。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_bases.rename_knowledge_base_record",
            return_value={
                "id": knowledge_base_id,
                "name": "新名称",
                "is_default": False,
                "created_at": "2026-07-01T00:00:00+08:00",
                "updated_at": "2026-07-21T00:00:00+08:00",
            },
        ) as rename_record, patch(
            "app.api.knowledge_bases.invalidate_knowledge_base_context",
        ):
            response = self.client.patch(
                f"/chat/knowledge-base/{knowledge_base_id}",
                json={"name": "  新名称  "},
            )

        self.assertEqual(response.status_code, 200)
        rename_record.assert_called_once_with(7, knowledge_base_id, "新名称")
        self.assertEqual(response.json()["knowledge_base"]["name"], "新名称")

    def test_default_knowledge_base_cannot_be_deleted(self) -> None:
        """默认知识库必须保留，删除请求返回 400。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_user_knowledge_base_lifecycle_record",
            return_value={
                "id": knowledge_base_id,
                "name": "默认知识库",
                "is_default": True,
                "deleted_at": None,
            },
        ), patch(
            "app.api.knowledge_bases.soft_delete_knowledge_base",
        ) as delete_record:
            response = self.client.delete(
                f"/chat/knowledge-base/{knowledge_base_id}",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "默认知识库不能删除")
        delete_record.assert_not_called()

    def test_delete_non_default_knowledge_base(self) -> None:
        """非默认知识库删除后应进入回收站且不删除文件。"""
        knowledge_base_id = uuid4()
        active_record = {
            "id": knowledge_base_id,
            "name": "研究资料",
            "is_default": False,
            "deleted_at": None,
        }
        deleted_record = {
            **active_record,
            "created_at": "2026-07-01T00:00:00+08:00",
            "updated_at": "2026-07-21T00:00:00+08:00",
            "deleted_at": "2026-07-21T00:00:00+08:00",
        }
        with patch(
            "app.api.knowledge_bases.get_user_knowledge_base_lifecycle_record",
            return_value=active_record,
        ), patch(
            "app.api.knowledge_bases.soft_delete_knowledge_base",
            return_value=deleted_record,
        ), patch(
            "app.api.knowledge_bases.invalidate_knowledge_base_context",
        ), patch(
            "app.api.knowledge_bases.invalidate_retrieval_settings_cache",
        ):
            response = self.client.delete(
                f"/chat/knowledge-base/{knowledge_base_id}",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("文件仍保留", response.json()["message"])
        self.assertEqual(
            response.json()["knowledge_base"]["id"],
            str(knowledge_base_id),
        )

    def test_restore_deleted_knowledge_base(self) -> None:
        """恢复接口应重新发布知识库并清理相关缓存。"""
        knowledge_base_id = uuid4()
        restored_record = {
            "id": knowledge_base_id,
            "name": "研究资料",
            "is_default": False,
            "created_at": "2026-07-01T00:00:00+08:00",
            "updated_at": "2026-07-21T00:00:00+08:00",
        }
        with patch(
            "app.api.knowledge_bases.restore_knowledge_base_record",
            return_value=restored_record,
        ), patch(
            "app.api.knowledge_bases.invalidate_knowledge_base_context",
        ) as invalidate_context, patch(
            "app.api.knowledge_bases.invalidate_retrieval_settings_cache",
        ) as invalidate_settings:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/restore",
            )

        self.assertEqual(response.status_code, 200)
        invalidate_context.assert_called_once_with(7, knowledge_base_id)
        invalidate_settings.assert_called_once_with(7, knowledge_base_id)


class KnowledgeFileLifecycleTests(unittest.TestCase):
    """验证知识文件永久删除的跨存储编排。"""

    def test_permanent_delete_cleans_all_stores(self) -> None:
        """永久删除应清理向量、数据库、磁盘和知识库缓存。"""
        file_id = uuid4()
        knowledge_base_id = uuid4()
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_root = Path(temp_dir)
            storage_path = upload_root / "7" / str(file_id) / "notes.md"
            storage_path.parent.mkdir(parents=True)
            storage_path.write_text("demo", encoding="utf-8")

            with patch(
                "app.services.knowledge_file_lifecycle_service.UPLOAD_ROOT",
                upload_root,
            ), patch(
                "app.services.knowledge_file_lifecycle_service.get_user_knowledge_file",
                return_value={"id": file_id, "storage_path": str(storage_path)},
            ), patch(
                "app.services.knowledge_file_lifecycle_service.get_knowledge_base_ids_for_file",
                return_value=[knowledge_base_id],
            ), patch(
                "app.services.knowledge_file_lifecycle_service.file_index_lock",
                return_value=nullcontext(),
            ), patch(
                "app.services.knowledge_file_lifecycle_service.cancel_active_vector_index_jobs",
            ) as cancel_jobs, patch(
                "app.services.knowledge_file_lifecycle_service.delete_file_vector_entries",
            ) as delete_vectors, patch(
                "app.services.knowledge_file_lifecycle_service.purge_user_knowledge_file_records",
                return_value={
                    "files_deleted": 1,
                    "relations_deleted": 1,
                    "chunks_deleted": 4,
                    "jobs_deleted": 2,
                    "source_feedback_deleted": 1,
                    "messages_scrubbed": 1,
                },
            ) as purge_records, patch(
                "app.services.knowledge_file_lifecycle_service.invalidate_knowledge_base_context",
            ) as invalidate_context:
                result = permanently_delete_knowledge_file(7, file_id)

            self.assertIsNotNone(result)
            self.assertEqual(result["files_deleted"], 1)
            self.assertFalse(storage_path.exists())
            cancel_jobs.assert_called_once()
            delete_vectors.assert_called_once_with(7, file_id)
            purge_records.assert_called_once_with(7, file_id)
            invalidate_context.assert_called_once_with(7, knowledge_base_id)

    def test_permanent_delete_rejects_storage_path_outside_upload_root(self) -> None:
        """异常数据库路径不能成为任意文件删除入口。"""
        file_id = uuid4()
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_root = Path(temp_dir) / "uploads"
            upload_root.mkdir()
            outside_path = Path(temp_dir) / "outside.md"
            outside_path.write_text("keep", encoding="utf-8")

            with patch(
                "app.services.knowledge_file_lifecycle_service.UPLOAD_ROOT",
                upload_root,
            ), patch(
                "app.services.knowledge_file_lifecycle_service.get_user_knowledge_file",
                return_value={"id": file_id, "storage_path": str(outside_path)},
            ), patch(
                "app.services.knowledge_file_lifecycle_service.delete_file_vector_entries",
            ) as delete_vectors:
                with self.assertRaisesRegex(ValueError, "上传目录"):
                    permanently_delete_knowledge_file(7, file_id)

            self.assertTrue(outside_path.exists())
            delete_vectors.assert_not_called()


class KnowledgeFileLifecycleRepositoryTests(unittest.TestCase):
    """验证 PostgreSQL 永久删除事务返回完整计数。"""

    def test_purge_returns_deleted_file_count(self) -> None:
        """成功删除主文件记录时应显式返回 files_deleted。"""
        file_id = uuid4()
        connection_context = MagicMock()
        connection = MagicMock()
        cursor = MagicMock()
        connection_context.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [{"id": file_id}, {"id": file_id}]
        type(cursor).rowcount = PropertyMock(
            side_effect=[0, 0, 1, 2, 3, 1],
        )

        with patch(
            "app.repositories.knowledge_file_repository.get_connection",
            return_value=connection_context,
        ):
            result = purge_user_knowledge_file_records(7, file_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["files_deleted"], 1)
        self.assertEqual(result["relations_deleted"], 1)
        self.assertEqual(result["chunks_deleted"], 2)
        self.assertEqual(result["jobs_deleted"], 3)


class KnowledgeFileLifecycleApiTests(unittest.TestCase):
    """验证永久删除文件 API 的错误边界。"""

    def setUp(self) -> None:
        """注入固定用户并创建测试客户端。"""
        app.dependency_overrides[get_current_user_id] = lambda: 7
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理认证覆盖和测试客户端。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_delete_missing_file_returns_404(self) -> None:
        """不存在或跨用户文件统一返回 404。"""
        file_id = uuid4()
        with patch(
            "app.api.knowledge_files.permanently_delete_knowledge_file",
            return_value=None,
        ):
            response = self.client.delete(f"/chat/knowledge-files/{file_id}")

        self.assertEqual(response.status_code, 404)

    def test_delete_file_returns_cleanup_counts(self) -> None:
        """成功响应应包含跨存储清理结果。"""
        file_id = uuid4()
        with patch(
            "app.api.knowledge_files.permanently_delete_knowledge_file",
            return_value={
                "file_id": str(file_id),
                "storage_deleted": True,
                "files_deleted": 1,
                "relations_deleted": 2,
                "chunks_deleted": 8,
                "jobs_deleted": 3,
                "source_feedback_deleted": 1,
                "messages_scrubbed": 1,
            },
        ):
            response = self.client.delete(f"/chat/knowledge-files/{file_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["files_deleted"], 1)
        self.assertEqual(response.json()["chunks_deleted"], 8)
        self.assertTrue(response.json()["storage_deleted"])
