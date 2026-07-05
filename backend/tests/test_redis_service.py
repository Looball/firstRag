"""Redis 基础设施 service 的回归测试。"""

import unittest
from unittest.mock import patch

from app.services import redis_service
from app.services.redis_service import (
    RedisHealth,
    check_redis_health,
    reset_redis_client_cache,
    sanitize_redis_url,
)


class RedisServiceTests(unittest.TestCase):
    """验证 Redis client、健康检查和脱敏行为。"""

    def setUp(self) -> None:
        """清理 Redis client 缓存，避免测试互相影响。"""
        reset_redis_client_cache()

    def tearDown(self) -> None:
        """清理 Redis client 缓存，避免测试互相影响。"""
        reset_redis_client_cache()

    def test_sanitize_redis_url_redacts_password(self) -> None:
        """Redis URL 摘要不应包含用户名密码。"""
        sanitized = sanitize_redis_url(
            "rediss://user:secret-password@redis.internal:6380/2",
        )

        self.assertEqual(
            sanitized,
            "rediss://[已脱敏]@redis.internal:6380/2",
        )
        self.assertNotIn("secret-password", sanitized)
        self.assertNotIn("user:", sanitized)

    def test_check_redis_health_returns_disabled_when_off(self) -> None:
        """显式关闭 Redis 时，健康检查应返回 disabled 而不是失败。"""
        with patch.object(redis_service.config, "REDIS_ENABLED", False):
            health = check_redis_health()

        self.assertEqual(
            health,
            RedisHealth(
                enabled=False,
                configured=bool(redis_service.config.REDIS_URL),
                is_healthy=True,
                status="disabled",
            ),
        )

    def test_check_redis_health_reports_missing_dependency(self) -> None:
        """缺少 redis 依赖时应给出 dependency_missing。"""
        with patch.object(redis_service.config, "REDIS_ENABLED", True), patch.object(
            redis_service.config,
            "REDIS_URL",
            "redis://redis:6379/0",
        ), patch.object(redis_service, "Redis", None):
            health = check_redis_health()

        self.assertFalse(health.is_healthy)
        self.assertEqual(health.status, "dependency_missing")
        self.assertEqual(health.error_source, "dependency")

    def test_check_redis_health_uses_configured_client(self) -> None:
        """Redis ping 成功时应返回 healthy，并复用配置创建 client。"""
        calls: list[dict[str, object]] = []

        class FakeRedisClient:
            """模拟 redis client。"""

            def ping(self) -> bool:
                """模拟 ping 成功。"""
                return True

        class FakeRedisFactory:
            """模拟 redis.Redis 工厂。"""

            @staticmethod
            def from_url(url: str, **kwargs: object) -> FakeRedisClient:
                """记录 from_url 参数并返回假 client。"""
                calls.append({"url": url, **kwargs})
                return FakeRedisClient()

        with patch.object(redis_service.config, "REDIS_ENABLED", True), patch.object(
            redis_service.config,
            "REDIS_URL",
            "redis://redis:6379/0",
        ), patch.object(
            redis_service.config,
            "REDIS_CONNECT_TIMEOUT_SECONDS",
            2.0,
        ), patch.object(
            redis_service.config,
            "REDIS_COMMAND_TIMEOUT_SECONDS",
            3.0,
        ), patch.object(
            redis_service,
            "Redis",
            FakeRedisFactory,
        ):
            health = check_redis_health()

        self.assertTrue(health.is_healthy)
        self.assertEqual(health.status, "healthy")
        self.assertEqual(calls[0]["url"], "redis://redis:6379/0")
        self.assertEqual(calls[0]["socket_connect_timeout"], 2.0)
        self.assertEqual(calls[0]["socket_timeout"], 3.0)

    def test_check_redis_health_redacts_connection_errors(self) -> None:
        """Redis 异常摘要不能泄露连接串密码。"""

        class FailingRedisClient:
            """模拟 ping 失败的 redis client。"""

            def ping(self) -> bool:
                """抛出包含 Redis URL 的异常。"""
                raise RuntimeError(
                    "connect redis://:secret@localhost:6379/0 failed",
                )

        class FakeRedisFactory:
            """模拟 redis.Redis 工厂。"""

            @staticmethod
            def from_url(url: str, **kwargs: object) -> FailingRedisClient:
                """返回失败 client。"""
                return FailingRedisClient()

        with patch.object(redis_service.config, "REDIS_ENABLED", True), patch.object(
            redis_service.config,
            "REDIS_URL",
            "redis://:secret@localhost:6379/0",
        ), patch.object(redis_service, "Redis", FakeRedisFactory):
            health = check_redis_health()

        self.assertFalse(health.is_healthy)
        self.assertEqual(health.status, "unavailable")
        self.assertEqual(health.error_source, "redis")
        self.assertNotIn("secret", health.error_message or "")
        self.assertIn("[已脱敏]", health.error_message or "")


if __name__ == "__main__":
    unittest.main()
