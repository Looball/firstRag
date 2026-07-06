"""Redis 分布式限流核心逻辑的回归测试。"""

import unittest
from unittest.mock import patch

from app.core import rate_limit
from app.core.rate_limit import (
    RateLimitExceededError,
    assert_rate_limit_available,
    clear_rate_limit,
    consume_rate_limit,
    reset_rate_limits,
)


class FakeRedisClient:
    """模拟 Redis client 的 eval/delete/scan 行为。"""

    def __init__(self, eval_results: list[list[int]] | None = None) -> None:
        """初始化脚本返回队列和调用记录。"""
        self.eval_results = eval_results or []
        self.eval_calls: list[dict[str, object]] = []
        self.deleted: list[str] = []
        self.scan_keys: list[str] = []

    def eval(self, script: str, numkeys: int, *args: object) -> list[int]:
        """记录 Lua 调用并返回预设结果。"""
        self.eval_calls.append({
            "script": script,
            "numkeys": numkeys,
            "args": args,
        })
        if self.eval_results:
            return self.eval_results.pop(0)
        return [1, 0, 1]

    def delete(self, *keys: str) -> None:
        """记录被删除的 key。"""
        self.deleted.extend(keys)

    def scan_iter(self, match: str, count: int) -> list[str]:
        """返回预设扫描结果。"""
        return [
            key
            for key in self.scan_keys
            if key.startswith(match.removesuffix("*"))
        ]


class RateLimitTests(unittest.TestCase):
    """验证 Redis 限流和进程内 fallback 行为。"""

    def setUp(self) -> None:
        """清空进程内限流桶。"""
        with patch.object(rate_limit.config, "RATE_LIMIT_BACKEND", "memory"):
            reset_rate_limits()

    def tearDown(self) -> None:
        """测试后清空进程内限流桶。"""
        with patch.object(rate_limit.config, "RATE_LIMIT_BACKEND", "memory"):
            reset_rate_limits()

    def test_consume_rate_limit_uses_redis_lua_script(self) -> None:
        """Redis 后端应通过 Lua 脚本原子消费请求额度。"""
        client = FakeRedisClient([[1, 0, 1]])

        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(
            rate_limit.config,
            "RATE_LIMIT_REDIS_FAILURE_MODE",
            "fail_closed",
        ), patch.object(rate_limit, "get_redis_client", return_value=client):
            consume_rate_limit("chat", "127.0.0.1:user:42", 10, 60)

        self.assertEqual(len(client.eval_calls), 1)
        call_args = client.eval_calls[0]["args"]
        assert isinstance(call_args, tuple)
        redis_key = str(call_args[0])
        self.assertTrue(redis_key.startswith("firstrag:rate_limit:chat:"))
        self.assertNotIn("127.0.0.1", redis_key)
        self.assertNotIn("user:42", redis_key)
        self.assertEqual(call_args[1], 60000)
        self.assertEqual(call_args[2], 10)
        self.assertEqual(call_args[3], 1)

    def test_assert_rate_limit_available_does_not_consume(self) -> None:
        """只检查额度时，Redis 脚本 consume 参数应为 0。"""
        client = FakeRedisClient([[1, 0, 0]])

        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(rate_limit, "get_redis_client", return_value=client):
            assert_rate_limit_available("login-failures", "alice", 2, 60)

        call_args = client.eval_calls[0]["args"]
        assert isinstance(call_args, tuple)
        self.assertEqual(call_args[3], 0)

    def test_redis_limit_exceeded_preserves_retry_after(self) -> None:
        """Redis 返回超限时，应抛出带 Retry-After 的限流异常。"""
        client = FakeRedisClient([[0, 17, 2]])

        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(rate_limit, "get_redis_client", return_value=client):
            with self.assertRaises(RateLimitExceededError) as context:
                consume_rate_limit("upload", "user:1", 2, 60)

        self.assertEqual(context.exception.retry_after_seconds, 17)
        self.assertEqual(context.exception.limit, 2)
        self.assertEqual(context.exception.window_seconds, 60)

    def test_redis_failure_fail_open_uses_memory_fallback(self) -> None:
        """fail-open 时 Redis 故障不应绕过本进程基础限流保护。"""
        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(
            rate_limit.config,
            "RATE_LIMIT_REDIS_FAILURE_MODE",
            "fail_open",
        ), patch.object(
            rate_limit,
            "get_redis_client",
            side_effect=RuntimeError("connect redis://:secret@redis:6379/0"),
        ):
            consume_rate_limit("chat", "user:1", 1, 60)
            with self.assertRaises(RateLimitExceededError):
                consume_rate_limit("chat", "user:1", 1, 60)

    def test_redis_failure_fail_closed_blocks_request(self) -> None:
        """fail-closed 时 Redis 故障应直接阻断请求并返回短 Retry-After。"""
        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(
            rate_limit.config,
            "RATE_LIMIT_REDIS_FAILURE_MODE",
            "fail_closed",
        ), patch.object(
            rate_limit,
            "get_redis_client",
            side_effect=RuntimeError("Redis timeout"),
        ):
            with self.assertRaises(RateLimitExceededError) as context:
                consume_rate_limit("model-test", "user:1", 5, 300)

        self.assertEqual(context.exception.retry_after_seconds, 60)

    def test_clear_rate_limit_deletes_redis_bucket(self) -> None:
        """登录成功清理限流时应同时删除 Redis bucket。"""
        client = FakeRedisClient()

        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(rate_limit, "get_redis_client", return_value=client):
            clear_rate_limit("login-failures", "alice")

        self.assertEqual(len(client.deleted), 1)
        self.assertTrue(
            client.deleted[0].startswith(
                "firstrag:rate_limit:login-failures:",
            )
        )
        self.assertNotIn("alice", client.deleted[0])

    def test_reset_rate_limits_deletes_redis_namespace(self) -> None:
        """测试隔离应清理 Redis rate limit 命名空间。"""
        client = FakeRedisClient()
        client.scan_keys = [
            "firstrag:rate_limit:chat:a",
            "firstrag:rate_limit:upload:b",
            "firstrag:cache:other",
        ]

        with patch.object(
            rate_limit.config,
            "RATE_LIMIT_BACKEND",
            "redis",
        ), patch.object(rate_limit, "get_redis_client", return_value=client):
            reset_rate_limits()

        self.assertEqual(
            client.deleted,
            [
                "firstrag:rate_limit:chat:a",
                "firstrag:rate_limit:upload:b",
            ],
        )


if __name__ == "__main__":
    unittest.main()
