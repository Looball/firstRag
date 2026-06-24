"""用户聊天模型设置服务的单元测试。"""

from decimal import Decimal
import unittest
from unittest.mock import patch

from app.services.user_settings_service import (
    _merge_settings_record,
    _validate_user_base_url,
    get_serialized_user_llm_settings,
    update_user_llm_settings,
)


def build_user_record() -> dict:
    """构造一份用户自带 Key 的数据库记录。"""
    return {
        "user_id": 1,
        "credential_mode": "user",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "base_url": None,
        "api_key_ciphertext": "encrypted-key",
        "encryption_key_version": 1,
        "temperature": Decimal("0.20"),
        "max_tokens": 8000,
        "timeout_seconds": Decimal("60.00"),
        "max_retries": 2,
    }


class UserLLMSettingsServiceTests(unittest.TestCase):
    """验证用户模型设置的密钥保护与更新规则。"""

    def test_get_settings_never_decrypts_api_key(self) -> None:
        """读取设置页只能返回是否配置 Key，不能解密 Key。"""
        record = build_user_record()
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=record,
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
        ) as decrypt_secret:
            settings = get_serialized_user_llm_settings(1)

        self.assertTrue(settings["has_api_key"])
        self.assertNotIn("api_key", settings)
        decrypt_secret.assert_not_called()

    def test_update_user_settings_encrypts_new_api_key(self) -> None:
        """新提交的 API Key 应加密后才传给仓库层。"""
        record = build_user_record()
        saved_record = {**record, "model": "deepseek-chat"}
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            side_effect=[record, saved_record],
        ), patch(
            "app.services.user_settings_service.encrypt_secret",
            return_value="new-encrypted-key",
        ) as encrypt_secret, patch(
            "app.services.user_settings_service.upsert_user_llm_settings",
            return_value=saved_record,
        ) as upsert_settings, patch(
            "app.services.user_settings_service.decrypt_secret",
        ) as decrypt_secret:
            settings = update_user_llm_settings(
                1,
                {"model": "deepseek-chat", "api_key": "new-plain-key"},
            )

        encrypt_secret.assert_called_once_with("new-plain-key")
        upsert_settings.assert_called_once()
        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(
            persisted_settings["api_key_ciphertext"],
            "new-encrypted-key",
        )
        self.assertEqual(settings["model"], "deepseek-chat")
        decrypt_secret.assert_not_called()

    def test_custom_user_base_url_is_disabled_by_default(self) -> None:
        """未开启开关时，用户不应能设置任意兼容接口地址。"""
        with self.assertRaisesRegex(ValueError, "不允许用户自定义"):
            _validate_user_base_url(
                "openai_compatible",
                "https://llm.example.com/v1",
            )

    def test_user_mode_rejects_whitespace_only_model(self) -> None:
        """仅由空白组成的模型名不能被持久化为无效用户配置。"""
        record = build_user_record()

        with self.assertRaisesRegex(ValueError, "非空 model"):
            _merge_settings_record(record, {"model": "   "})


if __name__ == "__main__":
    unittest.main()
