"""知识库检索设置缓存的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.cache_service import CacheBackendResult
from app.services.retrieval_settings_cache import (
    get_cached_knowledge_base_retrieval_settings,
    get_retrieval_settings_cache_diagnostics,
    invalidate_retrieval_settings_cache,
    reset_retrieval_settings_cache_diagnostics,
)


class RetrievalSettingsCacheTests(unittest.TestCase):
    """验证 retrieval settings 进程内缓存行为。"""

    def setUp(self) -> None:
        """清理测试用户的缓存和诊断状态。"""
        invalidate_retrieval_settings_cache(1)
        reset_retrieval_settings_cache_diagnostics()

    def tearDown(self) -> None:
        """测试后清理缓存，避免影响其它用例。"""
        invalidate_retrieval_settings_cache(1)
        reset_retrieval_settings_cache_diagnostics()

    def test_cache_miss_then_hit_reuses_settings(self) -> None:
        """首次读取应加载源数据，TTL 内重复读取应命中缓存。"""
        knowledge_base_id = uuid4()
        calls = 0

        def load_settings() -> dict:
            nonlocal calls
            calls += 1
            return {"top_k": 3}

        first = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )
        first_diagnostics = get_retrieval_settings_cache_diagnostics()
        second = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )
        second_diagnostics = get_retrieval_settings_cache_diagnostics()

        self.assertEqual(first, {"top_k": 3})
        self.assertEqual(second, {"top_k": 3})
        self.assertEqual(calls, 1)
        self.assertIsNotNone(first_diagnostics)
        self.assertIsNotNone(second_diagnostics)
        assert first_diagnostics is not None
        assert second_diagnostics is not None
        self.assertFalse(first_diagnostics["retrieval_settings_cache_hit"])
        self.assertTrue(second_diagnostics["retrieval_settings_cache_hit"])
        self.assertEqual(
            second_diagnostics["retrieval_settings_source"],
            "cache",
        )

    def test_ttl_expired_reloads_settings(self) -> None:
        """TTL 过期后应重新加载设置。"""
        knowledge_base_id = uuid4()
        calls = 0

        def load_settings() -> dict:
            nonlocal calls
            calls += 1
            return {"top_k": calls}

        first = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
            ttl_seconds=0,
        )
        second = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
            ttl_seconds=0,
        )

        self.assertEqual(first, {"top_k": 1})
        self.assertEqual(second, {"top_k": 2})
        self.assertEqual(calls, 2)

    def test_invalidate_reloads_settings(self) -> None:
        """主动失效后下一次读取应重新加载设置。"""
        knowledge_base_id = uuid4()
        calls = 0

        def load_settings() -> dict:
            nonlocal calls
            calls += 1
            return {"top_k": calls}

        get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )
        invalidate_retrieval_settings_cache(1, knowledge_base_id)
        settings = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )

        self.assertEqual(settings, {"top_k": 2})
        self.assertEqual(calls, 2)

    def test_redis_hit_reuses_shared_settings(self) -> None:
        """Redis 命中时应直接返回共享缓存，不触发源数据加载。"""
        knowledge_base_id = uuid4()

        def load_settings() -> dict:
            raise AssertionError("Redis hit should not load settings")

        with patch(
            "app.services.retrieval_settings_cache.cache_service.get_json_cache",
            return_value=CacheBackendResult(
                hit=True,
                value={"top_k": 7},
            ),
        ):
            settings = get_cached_knowledge_base_retrieval_settings(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_settings=load_settings,
            )

        diagnostics = get_retrieval_settings_cache_diagnostics()
        self.assertEqual(settings, {"top_k": 7})
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["retrieval_settings_cache_hit"])
        self.assertEqual(
            diagnostics["retrieval_settings_cache_backend"],
            "redis",
        )

    def test_redis_unavailable_falls_back_to_memory_cache(self) -> None:
        """Redis 不可用时，TTL 内重复读取应复用进程内 fallback。"""
        knowledge_base_id = uuid4()
        calls = 0

        def load_settings() -> dict:
            nonlocal calls
            calls += 1
            return {"top_k": calls}

        redis_unavailable = CacheBackendResult(
            hit=False,
            available=False,
            fallback_reason="redis timeout",
        )
        with patch(
            "app.services.retrieval_settings_cache.cache_service.get_json_cache",
            return_value=redis_unavailable,
        ), patch(
            "app.services.retrieval_settings_cache.cache_service.set_json_cache",
            return_value=redis_unavailable,
        ):
            first = get_cached_knowledge_base_retrieval_settings(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_settings=load_settings,
            )
            second = get_cached_knowledge_base_retrieval_settings(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_settings=load_settings,
            )

        diagnostics = get_retrieval_settings_cache_diagnostics()
        self.assertEqual(first, {"top_k": 1})
        self.assertEqual(second, {"top_k": 1})
        self.assertEqual(calls, 1)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertEqual(
            diagnostics["retrieval_settings_cache_backend"],
            "memory",
        )
        self.assertEqual(
            diagnostics["retrieval_settings_cache_fallback_reason"],
            "redis timeout",
        )

    def test_missing_settings_are_not_cached(self) -> None:
        """知识库不存在时不缓存 None，避免短 TTL 内隐藏新资源。"""
        knowledge_base_id = uuid4()
        calls = 0

        def load_settings() -> None:
            nonlocal calls
            calls += 1
            return None

        first = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )
        second = get_cached_knowledge_base_retrieval_settings(
            user_id=1,
            knowledge_base_id=knowledge_base_id,
            load_settings=load_settings,
        )

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
