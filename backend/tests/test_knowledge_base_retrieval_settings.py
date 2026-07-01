"""知识库检索设置接口的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class KnowledgeBaseRetrievalSettingsTests(unittest.TestCase):
    """验证知识库级 RAG 检索策略接口。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_get_retrieval_settings_returns_current_settings(self) -> None:
        """读取接口应返回当前知识库检索设置。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_knowledge_base_retrieval_settings",
            return_value={
                "retrieval_mode": "auto",
                "enable_query_router": True,
                "enable_rerank": True,
                "top_k": 4,
                "vector_top_k": 16,
                "fulltext_top_k": 16,
                "rrf_k": 8,
                "rerank_score_threshold": 0.0,
            },
        ):
            response = self.client.get(
                f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["settings"]["top_k"], 4)

    def test_patch_retrieval_settings_merges_and_saves(self) -> None:
        """更新接口应合并默认值、当前值和本次 patch 后保存。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_knowledge_base_retrieval_settings",
            return_value={
                "retrieval_mode": "auto",
                "enable_query_router": True,
                "enable_rerank": True,
                "top_k": 4,
                "vector_top_k": 16,
                "fulltext_top_k": 16,
                "rrf_k": 8,
                "rerank_score_threshold": 0.0,
            },
        ), patch(
            "app.api.knowledge_bases.upsert_knowledge_base_retrieval_settings",
            return_value={
                "retrieval_mode": "always",
                "enable_query_router": True,
                "enable_rerank": False,
                "top_k": 3,
                "vector_top_k": 16,
                "fulltext_top_k": 16,
                "rrf_k": 8,
                "rerank_score_threshold": 0.0,
            },
        ) as upsert_mock, patch(
            "app.api.knowledge_bases.invalidate_retrieval_settings_cache",
        ) as invalidate_mock:
            response = self.client.patch(
                f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
                json={
                    "retrieval_mode": "always",
                    "enable_rerank": False,
                    "top_k": 3,
                },
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = upsert_mock.call_args
        self.assertEqual(kwargs["settings"]["retrieval_mode"], "always")
        self.assertFalse(kwargs["settings"]["enable_rerank"])
        self.assertEqual(kwargs["settings"]["top_k"], 3)
        self.assertEqual(response.json()["settings"]["retrieval_mode"], "always")
        invalidate_mock.assert_called_once_with(1, knowledge_base_id)


if __name__ == "__main__":
    unittest.main()
