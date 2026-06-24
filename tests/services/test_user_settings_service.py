"""用户聊天模型设置服务的单元测试。"""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from app.services.user_settings_service import (
    _merge_settings_record,
    _validate_user_base_url,
    get_serialized_user_llm_settings,
    test_user_llm_settings,
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
        "api_key_hint": "••••-key",
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
        self.assertEqual(settings["api_key_hint"], "••••-key")
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
        self.assertEqual(persisted_settings["api_key_hint"], "••••-key")
        self.assertEqual(settings["model"], "deepseek-chat")
        decrypt_secret.assert_not_called()

    def test_legacy_saved_key_returns_only_a_masked_hint(self) -> None:
        """旧记录没有提示字段时，也只能向设置页返回脱敏标识。"""
        record = build_user_record()
        record["api_key_hint"] = None
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=record,
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="sk-live-1234",
        ) as decrypt_secret:
            settings = get_serialized_user_llm_settings(1)

        self.assertEqual(settings["api_key_hint"], "••••1234")
        self.assertNotIn("sk-live-1234", str(settings))
        decrypt_secret.assert_called_once_with("encrypted-key")

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

    def test_test_settings_returns_models_without_a_selected_model(self) -> None:
        """临时测试可先获取模型列表，再由用户选择具体聊天模型。"""
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=None,
        ), patch(
            "app.services.user_settings_service.encrypt_secret",
            return_value="encrypted-key",
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.user_settings_service._list_available_models",
            return_value=["deepseek-chat", "deepseek-reasoner"],
        ), patch(
            "app.services.user_settings_service.upsert_user_llm_settings",
            return_value=build_user_record(),
        ), patch(
            "app.services.user_settings_service.create_openai_compatible_chat_model",
        ) as create_model:
            result = test_user_llm_settings(
                1,
                {
                    "credential_mode": "user",
                    "provider": "deepseek",
                    "api_key": "plain-key",
                },
            )

        self.assertEqual(
            result["models"],
            ["deepseek-chat", "deepseek-reasoner"],
        )
        self.assertTrue(result["model_list_available"])
        self.assertTrue(result["api_key_saved"])
        create_model.assert_not_called()

    def test_selected_model_can_pass_when_models_endpoint_is_unavailable(self) -> None:
        """不支持 /models 的兼容服务仍应允许已选模型完成连通性测试。"""
        record = build_user_record()
        model = MagicMock()
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=record,
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.user_settings_service._list_available_models",
            side_effect=RuntimeError("unsupported"),
        ), patch(
            "app.services.user_settings_service.create_openai_compatible_chat_model",
            return_value=model,
        ):
            result = test_user_llm_settings(1, {})

        self.assertFalse(result["model_list_available"])
        self.assertEqual(result["models"], [])
        model.invoke.assert_called_once_with("请只回复：OK")

    def test_test_failure_keeps_new_api_key_draft(self) -> None:
        """模型调用失败时，新输入的 API Key 也应已经加密保存。"""
        model = MagicMock()
        model.invoke.side_effect = RuntimeError("model unavailable")
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=None,
        ), patch(
            "app.services.user_settings_service.encrypt_secret",
            return_value="encrypted-key",
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.user_settings_service.upsert_user_llm_settings",
            return_value=build_user_record(),
        ) as upsert_settings, patch(
            "app.services.user_settings_service._list_available_models",
            return_value=["deepseek-v4-flash"],
        ), patch(
            "app.services.user_settings_service.create_openai_compatible_chat_model",
            return_value=model,
        ):
            with self.assertRaisesRegex(RuntimeError, "model unavailable"):
                test_user_llm_settings(
                    1,
                    {
                        "credential_mode": "user",
                        "provider": "deepseek",
                        "model": "deepseek-v4-flash",
                        "api_key": "plain-key",
                    },
                )

        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(
            persisted_settings["api_key_ciphertext"],
            "encrypted-key",
        )


if __name__ == "__main__":
    unittest.main()
