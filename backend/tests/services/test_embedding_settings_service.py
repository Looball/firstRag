"""用户向量模型设置服务的单元测试。"""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from app.services.vectors.embedding_settings_service import (
    check_user_embedding_settings,
    get_effective_embedding_model_settings,
    get_serialized_user_embedding_settings,
    update_user_embedding_settings,
)


def build_embedding_record() -> dict:
    """构造一份用户向量模型数据库记录。"""
    return {
        "user_id": 1,
        "provider": "qwen",
        "model": "text-embedding-v4",
        "base_url": None,
        "dimensions": 1024,
        "api_key_ciphertext": "encrypted-key",
        "api_key_hint": "••••-key",
        "encryption_key_version": 1,
        "timeout_seconds": Decimal("60.00"),
        "max_retries": 2,
    }


class UserEmbeddingSettingsServiceTests(unittest.TestCase):
    """验证用户向量模型设置的密钥保护与调用配置。"""

    def test_missing_settings_returns_default_serialized_shape(self) -> None:
        """读取设置页时未配置用户也应得到默认表单结构。"""
        with patch(
            "app.services.vectors.embedding_settings_service.get_user_embedding_settings",
            return_value=None,
        ):
            settings = get_serialized_user_embedding_settings(1)

        self.assertEqual(settings["provider"], "qwen")
        self.assertEqual(settings["model"], "text-embedding-v4")
        self.assertFalse(settings["has_api_key"])
        self.assertNotIn("api_key", settings)

    def test_effective_settings_require_user_configuration(self) -> None:
        """真正调用 embedding 前必须已有当前用户配置。"""
        with patch(
            "app.services.vectors.embedding_settings_service.get_user_embedding_settings",
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "向量模型 API Key"):
                get_effective_embedding_model_settings(1)

    def test_update_embedding_settings_encrypts_new_api_key(self) -> None:
        """新提交的向量 API Key 应加密后才传给仓库层。"""
        saved_record = build_embedding_record()
        with patch(
            "app.services.vectors.embedding_settings_service.get_user_embedding_settings",
            side_effect=[None, saved_record],
        ), patch(
            "app.services.vectors.embedding_settings_service.encrypt_secret",
            return_value="encrypted-key",
        ) as encrypt_secret, patch(
            "app.services.vectors.embedding_settings_service.upsert_user_embedding_settings",
            return_value=saved_record,
        ) as upsert_settings:
            settings = update_user_embedding_settings(
                1,
                {
                    "provider": "qwen",
                    "model": "text-embedding-v4",
                    "dimensions": 1024,
                    "api_key": "plain-key",
                },
            )

        encrypt_secret.assert_called_once_with("plain-key")
        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(
            persisted_settings["api_key_ciphertext"],
            "encrypted-key",
        )
        self.assertEqual(settings["api_key_hint"], "••••-key")

    def test_switching_provider_resets_model_and_dimensions(self) -> None:
        """切换向量厂商时不应沿用旧厂商模型和维度。"""
        current_record = build_embedding_record()
        saved_record = {
            **current_record,
            "provider": "zhipuai",
            "model": "embedding-3",
            "dimensions": None,
        }
        with patch(
            "app.services.vectors.embedding_settings_service.get_user_embedding_settings",
            side_effect=[current_record, saved_record],
        ), patch(
            "app.services.vectors.embedding_settings_service.encrypt_secret",
            return_value="encrypted-zhipu-key",
        ), patch(
            "app.services.vectors.embedding_settings_service.upsert_user_embedding_settings",
            return_value=saved_record,
        ) as upsert_settings:
            update_user_embedding_settings(
                1,
                {
                    "provider": "zhipuai",
                    "api_key": "plain-zhipu-key",
                },
            )

        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(persisted_settings["model"], "embedding-3")
        self.assertIsNone(persisted_settings["base_url"])
        self.assertIsNone(persisted_settings["dimensions"])

    def test_check_embedding_settings_calls_embedding_provider(self) -> None:
        """连接测试应使用用户配置生成一次 query embedding。"""
        embedding_model = MagicMock()
        embedding_model.embed_query.return_value = [0.1, 0.2, 0.3]
        with patch(
            "app.services.vectors.embedding_settings_service.get_user_embedding_settings",
            return_value=build_embedding_record(),
        ), patch(
            "app.services.vectors.embedding_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.vectors.embedding_model.create_embedding_model_from_settings",
            return_value=embedding_model,
        ) as create_model:
            result = check_user_embedding_settings(1, {})

        self.assertEqual(result["dimensions"], 3)
        settings = create_model.call_args.args[0]
        self.assertEqual(settings.api_key, "plain-key")
        embedding_model.embed_query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
