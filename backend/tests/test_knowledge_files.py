"""知识文件接口的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class KnowledgeFileListTests(unittest.TestCase):
    """验证文件列表返回向量化任务状态。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_get_knowledge_base_files_returns_latest_index_job(self) -> None:
        """知识库文件列表应返回每个文件最近一次向量化任务。"""
        knowledge_base_id = uuid4()
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_knowledge_base_file_records",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "failed",
                    "index_version": 0,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:01+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_bases.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": knowledge_base_id,
                    "index_version": 0,
                    "status": "failed",
                    "attempts": 3,
                    "max_attempts": 3,
                    "error_message": "解析失败",
                    "result": None,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                    "started_at": "2026-06-25T00:00:01+08:00",
                    "finished_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
            )

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "failed")
        self.assertEqual(latest_job["error_message"], "解析失败")
        self.assertEqual(latest_job["attempts"], 3)

    def test_get_all_knowledge_files_returns_latest_index_job(self) -> None:
        """全局文件列表也应返回最近一次向量化任务。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "queued",
                    "index_version": 0,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 0,
                    "status": "queued",
                    "attempts": 0,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": None,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:00+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "queued")
        self.assertEqual(latest_job["max_attempts"], 3)

    def test_latest_index_job_normalizes_succeeded_status(self) -> None:
        """文件列表应把内部 succeeded 状态归一化为前端协议的 completed。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "indexed",
                    "index_version": 1,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 1,
                    "status": "succeeded",
                    "attempts": 1,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": {"chunk_count": 3},
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                    "started_at": "2026-06-25T00:00:01+08:00",
                    "finished_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "completed")

    def test_stale_index_job_is_hidden_after_vector_delete(self) -> None:
        """删除向量后，旧版本成功任务不应继续让前端显示已向量化。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "pending",
                    "index_version": 2,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 1,
                    "status": "succeeded",
                    "attempts": 1,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": {"chunk_count": 3},
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        file_payload = response.json()["files"][0]
        self.assertEqual(file_payload["status"], "pending")
        self.assertIsNone(file_payload["latest_index_job"])


if __name__ == "__main__":
    unittest.main()
