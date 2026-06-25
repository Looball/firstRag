"""会话路由的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class CreateConversationTests(unittest.TestCase):
    """验证创建会话的知识库权限校验。"""

    def setUp(self) -> None:
        """为每个测试注入固定的认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)
        self.knowledge_base_id = uuid4()

    def tearDown(self) -> None:
        """清理路由依赖覆盖，避免污染其他测试。"""
        app.dependency_overrides.pop(get_current_user_id, None)
        self.client.close()

    def test_create_conversation_returns_404_for_inaccessible_knowledge_base(
        self,
    ) -> None:
        """不存在或无权访问的知识库不应被误报为服务器错误。"""
        with patch(
            "app.api.conversations.knowledge_base_exists",
            return_value=False,
        ), patch(
            "app.api.conversations.create_conversation_record",
        ) as create_record:
            response = self.client.post(
                f"/chat/knowledge-bases/{self.knowledge_base_id}/conversations",
                json={"title": "测试会话"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "知识库不存在"})
        create_record.assert_not_called()

    def test_create_conversation_persists_for_accessible_knowledge_base(self) -> None:
        """可访问的知识库仍使用原有仓库调用创建会话。"""
        conversation_id = uuid4()
        conversation = {
            "id": conversation_id,
            "knowledge_base_id": self.knowledge_base_id,
            "title": "测试会话",
        }
        with patch(
            "app.api.conversations.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.conversations.create_conversation_record",
            return_value=conversation,
        ) as create_record:
            response = self.client.post(
                f"/chat/knowledge-bases/{self.knowledge_base_id}/conversations",
                json={"title": "测试会话"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        create_record.assert_called_once_with(
            1,
            self.knowledge_base_id,
            "测试会话",
        )

    def test_get_messages_returns_persisted_sources_and_retrieval(self) -> None:
        """历史消息接口应返回已持久化的引用来源和检索状态。"""
        conversation_id = uuid4()
        sources = [
            {
                "index": 1,
                "file_name": "民事诉讼法.pdf",
                "content": "相关片段",
            }
        ]
        retrieval = {
            "need_retrieval": True,
            "rewritten_query": "诉讼法",
            "reason": "问题涉及知识库",
            "retrieved_count": 5,
            "source_count": 1,
        }
        with patch(
            "app.api.conversations.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.conversations.get_user_conversation_messages",
            return_value=[
                {
                    "id": uuid4(),
                    "role": "assistant",
                    "content": "回答",
                    "status": "completed",
                    "error_message": None,
                    "sources": sources,
                    "retrieval": retrieval,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ):
            response = self.client.get(
                f"/chat/conversations/{conversation_id}/messages",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["sources"], sources)
        self.assertEqual(
            response.json()["messages"][0]["retrieval"],
            retrieval,
        )


if __name__ == "__main__":
    unittest.main()
