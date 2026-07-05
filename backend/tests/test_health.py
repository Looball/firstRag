"""系统健康检查接口的回归测试。"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.redis_service import RedisHealth


class SystemHealthTests(unittest.TestCase):
    """验证 `/health` 返回安全的基础设施摘要。"""

    def setUp(self) -> None:
        """创建测试客户端。"""
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """关闭测试客户端。"""
        self.client.close()

    def test_health_returns_healthy_when_redis_disabled(self) -> None:
        """Redis 禁用时整体健康状态仍应为 healthy。"""
        with patch(
            "app.api.health.check_redis_health",
            return_value=RedisHealth(
                enabled=False,
                configured=False,
                is_healthy=True,
                status="disabled",
            ),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(
            payload["dependencies"]["redis"]["status"],
            "disabled",
        )
        self.assertNotIn("url", payload["dependencies"]["redis"])

    def test_health_returns_degraded_when_redis_unavailable(self) -> None:
        """Redis 启用但不可用时整体状态应为 degraded。"""
        with patch(
            "app.api.health.check_redis_health",
            return_value=RedisHealth(
                enabled=True,
                configured=True,
                is_healthy=False,
                status="unavailable",
                error_source="redis",
                error_message="connect [已脱敏] failed",
            ),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["dependencies"]["redis"]["is_healthy"])
        self.assertNotIn("redis://", str(payload))


if __name__ == "__main__":
    unittest.main()
