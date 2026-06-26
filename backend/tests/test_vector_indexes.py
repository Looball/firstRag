"""向量化任务接口的回归测试。"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class VectorIndexJobHealthTests(unittest.TestCase):
    """验证向量化任务健康检查接口。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他测试。"""
        app.dependency_overrides.clear()
        self.client.close()

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
            },
        ):
            response = self.client.get("/chat/vector-index-jobs/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["worker"]["status"], "active")
        self.assertTrue(payload["worker"]["is_healthy"])
        self.assertTrue(payload["worker"]["has_recent_activity"])
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
            },
        ):
            response = self.client.get("/chat/vector-index-jobs/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["worker"]["status"], "attention_needed")
        self.assertFalse(payload["worker"]["is_healthy"])
        self.assertEqual(payload["worker"]["stale_queued"], 1)
        self.assertEqual(payload["worker"]["stale_processing"], 1)


if __name__ == "__main__":
    unittest.main()
