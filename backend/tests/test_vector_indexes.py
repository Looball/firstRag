"""向量化任务接口的回归测试。"""

import contextlib
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.core.security import get_current_user_id
from app.main import app


class VectorIndexJobHealthTests(unittest.TestCase):
    """验证向量化任务健康检查接口。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        reset_rate_limits()
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他测试。"""
        app.dependency_overrides.clear()
        self.client.close()
        reset_rate_limits()

    def test_get_vector_index_jobs_health_returns_queue_summary(self) -> None:
        """健康检查接口应返回队列统计和 worker 状态。"""
        with patch(
            "app.api.vector_indexes.get_user_vector_index_job_health",
            return_value={
                "checked_at": "2026-06-25T12:00:00+08:00",
                "total": 6,
                "queued": 1,
                "processing": 1,
                "succeeded": 3,
                "failed": 1,
                "cancelled": 0,
                "stale_queued": 0,
                "stale_processing": 0,
                "last_job_updated_at": "2026-06-25T11:59:59+08:00",
                "last_processing_heartbeat_at": "2026-06-25T11:59:58+08:00",
                "oldest_active_created_at": "2026-06-25T11:58:00+08:00",
                "oldest_queued_created_at": "2026-06-25T11:58:00+08:00",
                "oldest_processing_heartbeat_at": "2026-06-25T11:59:58+08:00",
                "oldest_active_seconds": 120,
                "oldest_queued_seconds": 120,
                "oldest_processing_seconds": 2,
            },
        ):
            response = self.client.get("/chat/vector-index-jobs/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["worker"]["status"], "active")
        self.assertTrue(payload["worker"]["is_healthy"])
        self.assertTrue(payload["worker"]["has_recent_activity"])
        self.assertEqual(payload["worker"]["hint"], "worker 正在处理向量化任务。")
        self.assertEqual(payload["worker"]["oldest_active_seconds"], 120)
        self.assertEqual(payload["worker"]["oldest_processing_seconds"], 2)
        self.assertEqual(payload["queue"]["status"], "processing")
        self.assertEqual(payload["queue"]["active"], 2)
        self.assertEqual(payload["queue"]["succeeded"], 3)
        self.assertEqual(payload["queue"]["failed"], 1)

    def test_get_vector_index_jobs_health_marks_stale_tasks(self) -> None:
        """存在卡住的任务时，健康检查应提示需要关注。"""
        with patch(
            "app.api.vector_indexes.get_user_vector_index_job_health",
            return_value={
                "checked_at": "2026-06-25T12:00:00+08:00",
                "total": 2,
                "queued": 1,
                "processing": 1,
                "succeeded": 0,
                "failed": 0,
                "cancelled": 0,
                "stale_queued": 1,
                "stale_processing": 1,
                "last_job_updated_at": "2026-06-25T11:30:00+08:00",
                "last_processing_heartbeat_at": "2026-06-25T11:30:00+08:00",
                "oldest_active_created_at": "2026-06-25T11:20:00+08:00",
                "oldest_queued_created_at": "2026-06-25T11:20:00+08:00",
                "oldest_processing_heartbeat_at": "2026-06-25T11:30:00+08:00",
                "oldest_active_seconds": 2400,
                "oldest_queued_seconds": 2400,
                "oldest_processing_seconds": 1800,
            },
        ):
            response = self.client.get("/chat/vector-index-jobs/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["worker"]["status"], "attention_needed")
        self.assertFalse(payload["worker"]["is_healthy"])
        self.assertEqual(payload["worker"]["hint"], "向量化任务长时间未推进，可能 worker 未启动或已卡住。")
        self.assertEqual(payload["queue"]["status"], "stuck")
        self.assertEqual(payload["worker"]["oldest_active_seconds"], 2400)
        self.assertEqual(payload["worker"]["stale_queued"], 1)
        self.assertEqual(payload["worker"]["stale_processing"], 1)

    def test_get_vector_index_job_returns_404_for_inaccessible_job(self) -> None:
        """跨用户向量化任务不能通过 job id 被探测。"""
        job_id = uuid4()
        with patch(
            "app.api.vector_indexes.get_user_vector_index_job",
            return_value=None,
        ):
            response = self.client.get(f"/chat/vector-index-jobs/{job_id}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "任务不存在"})

    def test_index_file_vectors_returns_404_for_inaccessible_file(self) -> None:
        """跨用户或已软删除的文件不能提交向量化任务。"""
        file_id = uuid4()
        with patch(
            "app.api.vector_indexes.get_user_knowledge_file",
            return_value=None,
        ), patch(
            "app.api.vector_indexes.enqueue_file_vector_index",
        ) as enqueue:
            response = self.client.post(f"/chat/knowledge-files/{file_id}/vectors")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "文件不存在"})
        enqueue.assert_not_called()

    def test_index_file_vectors_is_rate_limited(self) -> None:
        """单文件向量化提交高频调用应返回 429。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "user_id": 1,
            "original_name": "demo.md",
            "status": "pending",
            "index_version": 0,
        }
        with patch(
            "app.api.vector_indexes.VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS",
            1,
        ), patch(
            "app.api.vector_indexes.API_RATE_LIMIT_WINDOW_SECONDS",
            60,
        ), patch(
            "app.api.vector_indexes.ensure_user_embedding_settings",
        ), patch(
            "app.api.vector_indexes.get_user_knowledge_file",
            return_value=file_record,
        ), patch(
            "app.api.vector_indexes.enqueue_file_vector_index",
            return_value={"id": str(uuid4()), "message": "queued"},
        ) as enqueue:
            first = self.client.post(f"/chat/knowledge-files/{file_id}/vectors")
            second = self.client.post(f"/chat/knowledge-files/{file_id}/vectors")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(
            second.json(),
            {"detail": "向量化提交过于频繁，请稍后再试。"},
        )
        enqueue.assert_called_once()

    def test_index_knowledge_base_vectors_rejects_batch_quota(self) -> None:
        """知识库批量向量化超过单次文件上限时应给出配额提示。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.vector_indexes.VECTOR_INDEX_MAX_BATCH_FILES",
            1,
        ), patch(
            "app.api.vector_indexes.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.vector_indexes.get_knowledge_base_files_for_indexing",
            return_value=[
                {"id": uuid4(), "user_id": 1, "status": "pending"},
                {"id": uuid4(), "user_id": 1, "status": "pending"},
            ],
        ), patch(
            "app.api.vector_indexes.ensure_user_embedding_settings",
        ), patch(
            "app.api.vector_indexes.enqueue_file_vector_index",
        ) as enqueue:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/vectors",
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("单次向量化提交文件数量超过上限", response.json()["detail"])
        enqueue.assert_not_called()

    def test_index_file_vectors_requires_embedding_settings(self) -> None:
        """未配置向量模型时不应提交 worker 任务。"""
        file_id = uuid4()
        file_record = {
            "id": file_id,
            "user_id": 1,
            "original_name": "demo.md",
            "status": "pending",
            "index_version": 0,
        }
        with patch(
            "app.api.vector_indexes.get_user_knowledge_file",
            return_value=file_record,
        ), patch(
            "app.api.vector_indexes.ensure_user_embedding_settings",
            side_effect=HTTPException(
                status_code=400,
                detail="向量模型配置无效：请先配置当前账号的向量模型 API Key",
            ),
        ), patch(
            "app.api.vector_indexes.enqueue_file_vector_index",
        ) as enqueue:
            response = self.client.post(f"/chat/knowledge-files/{file_id}/vectors")

        self.assertEqual(response.status_code, 400)
        self.assertIn("向量模型配置无效", response.json()["detail"])
        enqueue.assert_not_called()

    def test_delete_file_vectors_returns_404_for_inaccessible_file(self) -> None:
        """删除向量化结果前必须先确认文件属于当前用户。"""
        file_id = uuid4()
        with patch(
            "app.api.vector_indexes.get_user_knowledge_file",
            return_value=None,
        ), patch(
            "app.api.vector_indexes.cancel_active_vector_index_jobs",
        ) as cancel_jobs:
            response = self.client.delete(f"/chat/knowledge-files/{file_id}/vectors")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "文件不存在"})
        cancel_jobs.assert_not_called()

    def test_delete_file_vectors_returns_safe_error_when_cleanup_fails(self) -> None:
        """删除向量失败时不应把底层异常细节返回给前端。"""
        file_id = uuid4()
        with patch(
            "app.api.vector_indexes.get_user_knowledge_file",
            return_value={
                "id": file_id,
                "index_version": 1,
            },
        ), patch(
            "app.api.vector_indexes.cancel_active_vector_index_jobs",
        ), patch(
            "app.api.vector_indexes.file_index_lock",
            return_value=contextlib.nullcontext(),
        ), patch(
            "app.api.vector_indexes.delete_file_vector_entries",
            side_effect=RuntimeError(
                "Chroma path /srv/firstrag/vector_db failed with api_key=secret",
            ),
        ), patch(
            "app.api.vector_indexes.update_knowledge_file_status",
        ), patch(
            "app.api.vector_indexes.invalidate_file_knowledge_base_contexts",
        ):
            response = self.client.delete(f"/chat/knowledge-files/{file_id}/vectors")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "删除向量化存储失败，请稍后重试或检查向量库和数据库状态。"},
        )


if __name__ == "__main__":
    unittest.main()
