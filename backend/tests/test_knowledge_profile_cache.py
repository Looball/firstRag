"""知识库画像缓存的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.cache_service import CacheBackendResult
from app.services.knowledge_profile_cache import (
    get_cached_knowledge_base_context,
    get_knowledge_profile_cache_diagnostics,
    invalidate_knowledge_base_context,
    reset_knowledge_profile_cache_diagnostics,
)


class KnowledgeProfileCacheTests(unittest.TestCase):
    """验证 knowledge profile Redis 缓存和 fallback 行为。"""

    def setUp(self) -> None:
        """清理测试用户缓存和诊断状态。"""
        invalidate_knowledge_base_context(1)
        reset_knowledge_profile_cache_diagnostics()

    def tearDown(self) -> None:
        """测试后清理缓存，避免影响其它用例。"""
        invalidate_knowledge_base_context(1)
        reset_knowledge_profile_cache_diagnostics()

    def test_redis_hit_reuses_shared_profile(self) -> None:
        """Redis 命中时应直接还原知识库上下文。"""
        knowledge_base_id = uuid4()

        def load_rows() -> list[dict]:
            raise AssertionError("Redis hit should not load profile rows")

        with patch(
            "app.services.knowledge_profile_cache.cache_service.get_json_cache",
            return_value=CacheBackendResult(
                hit=True,
                value={
                    "profile": "当前知识库已索引文件：\n1. a.pdf（application/pdf）",
                    "file_ids": ["file-1"],
                    "indexed_count": 1,
                    "total_count": 1,
                },
            ),
        ):
            context = get_cached_knowledge_base_context(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_rows=load_rows,
                max_profile_files=5,
            )

        diagnostics = get_knowledge_profile_cache_diagnostics()
        self.assertEqual(context.file_ids, ["file-1"])
        self.assertEqual(context.indexed_count, 1)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["knowledge_profile_cache_hit"])
        self.assertEqual(
            diagnostics["knowledge_profile_cache_source"],
            "redis",
        )

    def test_redis_unavailable_falls_back_to_memory_profile(self) -> None:
        """Redis 不可用时，后续请求可命中进程内 fallback。"""
        knowledge_base_id = uuid4()
        indexed_file_id = uuid4()
        calls = 0

        def load_rows() -> list[dict]:
            nonlocal calls
            calls += 1
            return [
                {
                    "id": indexed_file_id,
                    "original_name": "民事诉讼法.pdf",
                    "mime_type": "application/pdf",
                    "status": "indexed",
                },
            ]

        redis_unavailable = CacheBackendResult(
            hit=False,
            available=False,
            fallback_reason="redis timeout",
        )
        with patch(
            "app.services.knowledge_profile_cache.cache_service.get_json_cache",
            return_value=redis_unavailable,
        ), patch(
            "app.services.knowledge_profile_cache.cache_service.set_json_cache",
            return_value=redis_unavailable,
        ):
            first = get_cached_knowledge_base_context(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_rows=load_rows,
                max_profile_files=5,
            )
            reset_knowledge_profile_cache_diagnostics()
            second = get_cached_knowledge_base_context(
                user_id=1,
                knowledge_base_id=knowledge_base_id,
                load_rows=load_rows,
                max_profile_files=5,
            )

        diagnostics = get_knowledge_profile_cache_diagnostics()
        self.assertEqual(first.file_ids, [str(indexed_file_id)])
        self.assertEqual(second.file_ids, [str(indexed_file_id)])
        self.assertEqual(calls, 1)
        self.assertIsNotNone(diagnostics)
        assert diagnostics is not None
        self.assertTrue(diagnostics["knowledge_profile_cache_hit"])
        self.assertEqual(
            diagnostics["knowledge_profile_cache_source"],
            "memory",
        )
        self.assertEqual(
            diagnostics["knowledge_profile_cache_fallback_reason"],
            "redis timeout",
        )


if __name__ == "__main__":
    unittest.main()
