"""聊天接口与用户模型设置集成的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class ChatSettingsTests(unittest.TestCase):
    """验证模型配置错误不会污染聊天消息记录。"""

    def setUp(self) -> None:
        """为每个测试注入固定的认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由测试。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_invalid_model_settings_does_not_save_messages(self) -> None:
        """用户模型配置无效时应返回 400，且不创建用户或助手消息。"""
        with patch(
            "app.api.chat.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.chat.conversation_belongs_base",
            return_value=True,
        ), patch(
            "app.api.chat.load_chat_history",
            return_value=[],
        ), patch(
            "app.api.chat.get_chain",
            side_effect=ValueError("用户 API Key 密文无效"),
        ), patch("app.api.chat.save_message") as save_message:
            response = self.client.post(
                "/chat",
                json={
                    "conversation_id": str(uuid4()),
                    "knowledge_base_id": str(uuid4()),
                    "message": "什么是诉讼法",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "模型配置无效：用户 API Key 密文无效"},
        )
        save_message.assert_not_called()

    def test_whitespace_only_message_is_rejected_before_database_access(
        self,
    ) -> None:
        """空白消息不应触发会话查询、模型调用或消息写入。"""
        with patch("app.api.chat.conversation_exists") as conversation_exists, patch(
            "app.api.chat.get_chain",
        ) as get_chain, patch("app.api.chat.save_message") as save_message:
            response = self.client.post(
                "/chat",
                json={
                    "conversation_id": str(uuid4()),
                    "knowledge_base_id": str(uuid4()),
                    "message": " \t\n ",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "message不能为空"})
        conversation_exists.assert_not_called()
        get_chain.assert_not_called()
        save_message.assert_not_called()

    def test_greeting_uses_local_response_without_model_chain(self) -> None:
        """普通问候应本地快速回复，不触发 RAG 链构建。"""
        assistant_message_id = uuid4()
        with patch(
            "app.api.chat.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.chat.conversation_belongs_base",
            return_value=True,
        ), patch(
            "app.api.chat.get_chain",
        ) as get_chain, patch(
            "app.api.chat.save_message",
            side_effect=[
                {"id": uuid4()},
                {"id": assistant_message_id},
            ],
        ), patch(
            "app.services.chat_service.finish_assistant_message",
        ):
            response = self.client.post(
                "/chat",
                json={
                    "conversation_id": str(uuid4()),
                    "knowledge_base_id": str(uuid4()),
                    "message": "你好",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("event: retrieval", body)
        self.assertIn('"need_retrieval": false', body)
        self.assertIn("event: answer", body)
        get_chain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
