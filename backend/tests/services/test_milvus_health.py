"""Milvus authenticated health probe 回归测试。"""

import unittest

from app.services.vectors.milvus_health import (
    check_milvus_authentication_enforced,
    check_milvus_health,
)


class FakeMilvusClient:
    """记录 health probe 是否完成 round-trip 和 close。"""

    def __init__(self, **kwargs: object) -> None:
        """保存安全的构造参数。"""
        self.options = kwargs
        self.closed = False
        self.list_timeout: float | None = None

    def list_collections(self, *, timeout: float) -> list[str]:
        """模拟 authenticated list-collections。"""
        self.list_timeout = timeout
        return []

    def close(self) -> None:
        """记录 client 已关闭。"""
        self.closed = True


class MilvusHealthTests(unittest.TestCase):
    """验证健康探针不会泄露凭据并能安全分类失败。"""

    def test_authenticated_round_trip_reports_healthy(self) -> None:
        """有效配置应执行 list-collections 并关闭 client。"""
        created: list[FakeMilvusClient] = []

        def factory(**kwargs: object) -> FakeMilvusClient:
            client = FakeMilvusClient(**kwargs)
            created.append(client)
            return client

        health = check_milvus_health(
            uri="http://milvus-standalone:19530",
            token="root:test-only-secret",
            database="default",
            timeout_seconds=7.5,
            client_factory=factory,
        )

        self.assertTrue(health.healthy)
        self.assertEqual(created[0].options["db_name"], "default")
        self.assertEqual(created[0].list_timeout, 7.5)
        self.assertTrue(created[0].closed)

    def test_provider_failure_is_sanitized(self) -> None:
        """Provider exception 和 token 不得进入健康摘要。"""
        secret = "root:do-not-leak-this-secret"

        def factory(**kwargs: object) -> FakeMilvusClient:
            raise RuntimeError(f"connection failed with {kwargs['token']}")

        health = check_milvus_health(
            uri="http://milvus-standalone:19530",
            token=secret,
            database="default",
            client_factory=factory,
        )

        self.assertFalse(health.healthy)
        self.assertNotIn(secret, health.detail or "")
        self.assertEqual(health.detail, "Authenticated Milvus round-trip failed.")

    def test_incomplete_configuration_does_not_create_client(self) -> None:
        """缺失 token 时直接返回配置失败。"""
        health = check_milvus_health(
            uri="http://milvus-standalone:19530",
            token="",
            database="default",
        )

        self.assertFalse(health.healthy)
        self.assertIn("incomplete", health.detail or "")

    def test_unauthenticated_client_must_be_rejected(self) -> None:
        """无 token 请求被拒绝时才认为 authentication 门禁生效。"""
        def factory(**kwargs: object) -> FakeMilvusClient:
            raise RuntimeError("missing authorization in header")

        health = check_milvus_authentication_enforced(
            uri="http://milvus-standalone:19530",
            database="default",
            client_factory=factory,
        )

        self.assertTrue(health.healthy)
        self.assertIn("rejected", health.detail or "")

    def test_unauthenticated_success_is_unhealthy(self) -> None:
        """服务若允许无 token 查询，门禁必须失败。"""
        health = check_milvus_authentication_enforced(
            uri="http://milvus-standalone:19530",
            database="default",
            client_factory=FakeMilvusClient,
        )

        self.assertFalse(health.healthy)
        self.assertIn("accepted", health.detail or "")


if __name__ == "__main__":
    unittest.main()
