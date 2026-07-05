"""聊天图片附件接口的回归测试。"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.core.security import get_current_user_id
from app.main import app
from app.services.chat_attachment_service import (
    ChatAttachmentError,
    resolve_attachment_file_path,
)
from app.services.llm_service import ChatModelSettings
from app.services.user_settings_service import EffectiveChatModelConfig


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
)


class ChatAttachmentTests(unittest.TestCase):
    """验证聊天图片附件上传和聊天绑定行为。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        reset_rate_limits()
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由。"""
        app.dependency_overrides.clear()
        self.client.close()
        reset_rate_limits()

    def _vision_config(self, model: str) -> EffectiveChatModelConfig:
        """构造测试用聊天模型配置。"""
        return EffectiveChatModelConfig(
            settings=ChatModelSettings(
                provider="qwen",
                model=model,
                api_key="sk-test",
                base_url=None,
                temperature=0.2,
                max_tokens=1000,
                timeout_seconds=60,
                max_retries=2,
            ),
            credential_mode="user",
        )

    def test_upload_chat_attachment_returns_safe_metadata(self) -> None:
        """上传图片附件应返回不含本地路径的 metadata。"""
        conversation_id = uuid4()
        attachment_id = uuid4()

        def create_attachment(**kwargs):
            """模拟数据库保存并回显附件记录。"""
            return {
                "id": attachment_id,
                "user_id": kwargs["user_id"],
                "conversation_id": kwargs["conversation_id"],
                "message_id": None,
                "original_name": kwargs["original_name"],
                "storage_path": kwargs["storage_path"],
                "mime_type": kwargs["mime_type"],
                "size_bytes": kwargs["size_bytes"],
                "file_hash": kwargs["file_hash"],
                "status": "uploaded",
                "created_at": "2026-07-04T00:00:00+08:00",
                "updated_at": "2026-07-04T00:00:00+08:00",
            }

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.api.chat.conversation_exists",
            return_value=True,
        ), patch(
            "app.services.chat_attachment_service.CHAT_ATTACHMENT_ROOT",
            Path(tmpdir),
        ), patch(
            "app.services.chat_attachment_service.create_message_attachment",
            side_effect=create_attachment,
        ):
            response = self.client.post(
                f"/chat/attachments?conversation_id={conversation_id}",
                files={
                    "files": (
                        "chart.png",
                        PNG_BYTES,
                        "image/png",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        attachment = response.json()["attachments"][0]
        self.assertEqual(attachment["id"], str(attachment_id))
        self.assertEqual(attachment["mime_type"], "image/png")
        self.assertEqual(
            attachment["content_url"],
            f"/chat/attachments/{attachment_id}/content",
        )
        self.assertNotIn("storage_path", attachment)

    def test_chat_rejects_images_when_model_lacks_vision(self) -> None:
        """当前模型不支持图片时，不应创建用户或助手消息。"""
        attachment_id = uuid4()
        with patch(
            "app.api.chat.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.chat.conversation_belongs_base",
            return_value=True,
        ), patch(
            "app.api.chat.validate_chat_attachments_for_message",
            return_value=[{"id": attachment_id}],
        ), patch(
            "app.api.chat.get_effective_chat_model_config",
            return_value=self._vision_config("qwen-plus"),
        ), patch("app.api.chat.save_message") as save_message:
            response = self.client.post(
                "/chat",
                json={
                    "conversation_id": str(uuid4()),
                    "knowledge_base_id": str(uuid4()),
                    "message": "请看这张图",
                    "attachment_ids": [str(attachment_id)],
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "当前聊天模型不支持图片输入，请切换支持视觉能力的模型。"},
        )
        save_message.assert_not_called()

    def test_chat_binds_images_and_passes_them_to_stream(self) -> None:
        """支持 vision 的模型应绑定附件并传给流式回答链路。"""
        conversation_id = uuid4()
        knowledge_base_id = uuid4()
        attachment_id = uuid4()
        attachment = {
            "id": attachment_id,
            "storage_path": "/tmp/image.png",
            "mime_type": "image/png",
            "size_bytes": len(PNG_BYTES),
        }

        with patch(
            "app.api.chat.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.chat.conversation_belongs_base",
            return_value=True,
        ), patch(
            "app.api.chat.validate_chat_attachments_for_message",
            return_value=[attachment],
        ), patch(
            "app.api.chat.get_effective_chat_model_config",
            return_value=self._vision_config("qwen-vl-plus"),
        ), patch(
            "app.api.chat.load_chat_history",
            return_value=[],
        ), patch(
            "app.api.chat.get_chain",
            return_value=object(),
        ), patch(
            "app.api.chat.save_message",
            side_effect=[{"id": 101}, {"id": 202}],
        ), patch(
            "app.api.chat.bind_attachments_to_user_message",
        ) as bind_attachments, patch(
            "app.api.chat.stream_answer_and_save",
            return_value=iter([
                'event: done\ndata: {"message": "回答完成"}\n\n',
            ]),
        ) as stream_answer:
            response = self.client.post(
                "/chat",
                json={
                    "conversation_id": str(conversation_id),
                    "knowledge_base_id": str(knowledge_base_id),
                    "message": "请看这张图",
                    "attachment_ids": [str(attachment_id)],
                },
            )

        self.assertEqual(response.status_code, 200)
        bind_attachments.assert_called_once_with(
            user_id=1,
            conversation_id=conversation_id,
            message_id=101,
            attachment_ids=[attachment_id],
        )
        self.assertEqual(
            stream_answer.call_args.kwargs["image_attachments"],
            [attachment],
        )

    def test_resolve_attachment_file_path_rejects_missing_file(self) -> None:
        """附件文件丢失时应返回明确错误。"""
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.services.chat_attachment_service.CHAT_ATTACHMENT_ROOT",
            Path(tmpdir),
        ):
            missing_file = Path(tmpdir) / "users" / "1" / "missing.png"
            with self.assertRaises(ChatAttachmentError) as exc:
                resolve_attachment_file_path({
                    "storage_path": str(missing_file),
                })

        self.assertEqual(str(exc.exception), "图片附件文件不存在")


if __name__ == "__main__":
    unittest.main()
