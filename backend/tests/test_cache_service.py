"""Redis cache adapter 的回归测试。"""

import unittest
from unittest.mock import patch

from app.services import cache_service
from app.services.cache_service import (
    CacheBackendResult,
    build_cache_key,
    build_cache_prefix,
    delete_cache_prefix,
    get_json_cache,
    reset_cache_adapter_state,
    set_json_cache,
)


class FakeRedisClient:
    """模拟 Redis client 的最小 JSON cache 行为。"""

    def __init__(self) -> None:
        """初始化内存存储和过期参数记录。"""
        self.values: dict[str, str] = {}
        self.expires: dict[str, int] = {}
        self.deleted: list[str] = []

    def get(self, key: str) -> str | None:
        """读取 key 对应的字符串 value。"""
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int) -> None:
        """写入 key/value 并记录 TTL。"""
        self.values[key] = value
        self.expires[key] = ex

    def delete(self, *keys: str) -> None:
        """删除一个或多个 key。"""
        for key in keys:
            self.values.pop(key, None)
            self.deleted.append(key)

    def scan_iter(self, match: str, count: int) -> list[str]:
        """按 prefix match 返回 key 列表。"""
        prefix = match.removesuffix("*")
        return [
            key
            for key in self.values
            if key.startswith(prefix)
        ]


class CacheServiceTests(unittest.TestCase):
    """验证 Redis JSON cache adapter 的核心行为。"""

    def setUp(self) -> None:
        """重置 cache adapter 熔断状态。"""
        reset_cache_adapter_state()

    def tearDown(self) -> None:
        """清理 cache adapter 熔断状态，避免影响其它用例。"""
        reset_cache_adapter_state()

    def test_build_cache_key_encodes_parts(self) -> None:
        """key 片段应被编码，避免 provider/model 中的特殊字符破坏层级。"""
        key = build_cache_key("query embedding", "user:1", "qwen/text")

        self.assertEqual(
            key,
            "firstrag:query%20embedding:user%3A1:qwen%2Ftext",
        )
        self.assertEqual(
            build_cache_prefix("retrieval_settings", 1),
            "firstrag:retrieval_settings:1:",
        )

    def test_json_cache_round_trip_uses_ttl(self) -> None:
        """JSON value 应能写入并读回，TTL 使用秒级 ex。"""
        client = FakeRedisClient()
        key = build_cache_key("settings", 1)

        with patch.object(cache_service, "get_redis_client", return_value=client):
            set_result = set_json_cache(key, {"top_k": 3}, 60.2)
            get_result = get_json_cache(key)

        self.assertIsInstance(set_result, CacheBackendResult)
        self.assertFalse(set_result.hit)
        self.assertTrue(get_result.hit)
        self.assertEqual(get_result.value, {"top_k": 3})
        self.assertEqual(client.expires[key], 61)

    def test_delete_cache_prefix_scans_and_deletes_matching_keys(self) -> None:
        """prefix invalidation 应只删除匹配命名空间的缓存。"""
        client = FakeRedisClient()
        client.values = {
            "firstrag:retrieval_settings:1:a": "{}",
            "firstrag:retrieval_settings:1:b": "{}",
            "firstrag:retrieval_settings:2:a": "{}",
        }

        with patch.object(cache_service, "get_redis_client", return_value=client):
            delete_cache_prefix("firstrag:retrieval_settings:1:")

        self.assertNotIn("firstrag:retrieval_settings:1:a", client.values)
        self.assertNotIn("firstrag:retrieval_settings:1:b", client.values)
        self.assertIn("firstrag:retrieval_settings:2:a", client.values)

    def test_redis_error_returns_fallback_result(self) -> None:
        """Redis 故障应返回脱敏 fallback 信息，而不是向业务层抛错。"""
        with patch.object(
            cache_service,
            "get_redis_client",
            side_effect=RuntimeError("connect redis://:secret@redis:6379/0"),
        ):
            result = get_json_cache("firstrag:test")

        self.assertFalse(result.hit)
        self.assertFalse(result.available)
        self.assertNotIn("secret", result.fallback_reason or "")
        self.assertIn("[已脱敏]", result.fallback_reason or "")


if __name__ == "__main__":
    unittest.main()
