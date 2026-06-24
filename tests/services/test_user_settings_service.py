"""用户聊天模型设置服务的单元测试。"""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from app.services.user_settings_service import (
    _merge_settings_record,
    _validate_user_base_url,
    get_serialized_user_llm_settings,
    get_saved_provider_models,
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

    def setUp(self) -> None:
        """默认隔离厂商凭据仓库，避免单元测试连接真实数据库。"""
        self.get_provider_credential = patch(
            "app.services.user_settings_service.get_user_llm_provider_credential",
            return_value=None,
        )
        self.upsert_provider_credential = patch(
            "app.services.user_settings_service.upsert_user_llm_provider_credential",
            return_value=build_user_record(),
        )
        self.get_provider_credential.start()
        self.upsert_provider_credential.start()
        self.addCleanup(self.get_provider_credential.stop)
        self.addCleanup(self.upsert_provider_credential.stop)

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

    def test_provider_catalog_marks_saved_credentials(self) -> None:
        """厂商目录应只返回已保存凭据状态和脱敏提示。"""
        from app.services.user_settings_service import (
            get_serialized_user_llm_providers,
        )

        with patch(
            "app.services.user_settings_service.get_user_llm_provider_credentials",
            return_value=[
                {
                    "provider": "deepseek",
                    "api_key_hint": "••••abcd",
                }
            ],
        ):
            providers = get_serialized_user_llm_providers(1)

        deepseek = next(item for item in providers if item["id"] == "deepseek")
        qwen = next(item for item in providers if item["id"] == "qwen")
        self.assertTrue(deepseek["has_api_key"])
        self.assertEqual(deepseek["api_key_hint"], "••••abcd")
        self.assertFalse(qwen["has_api_key"])
        self.assertIsNone(qwen["api_key_hint"])

    def test_saved_provider_models_does_not_modify_active_settings(self) -> None:
        """切换厂商读取模型列表时不应改写当前活动模型设置。"""
        credential = {
            "provider": "qwen",
            "api_key_ciphertext": "encrypted-qwen-key",
            "api_key_hint": "••••qwen",
            "encryption_key_version": 1,
        }
        with patch(
            "app.services.user_settings_service.get_user_llm_provider_credential",
            return_value=credential,
        ), patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=build_user_record(),
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="plain-qwen-key",
        ), patch(
            "app.services.user_settings_service._list_available_models",
            return_value=["qwen-plus", "qwen-turbo"],
        ) as list_models:
            models = get_saved_provider_models(1, "qwen")

        self.assertEqual(models, ["qwen-plus", "qwen-turbo"])
        settings = list_models.call_args.args[0]
        self.assertEqual(settings.provider, "qwen")
        self.assertEqual(settings.model, "")

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

    def test_model_discovery_does_not_reuse_previous_model(self) -> None:
        """未提交模型名时，应获取列表而非调用设置页中遗留的旧模型。"""
        record = build_user_record()
        record["provider"] = "deepseek"
        record["model"] = "qwen3.7-max"
        with patch(
            "app.services.user_settings_service.get_user_llm_settings",
            return_value=record,
        ), patch(
            "app.services.user_settings_service.encrypt_secret",
            return_value="encrypted-key",
        ), patch(
            "app.services.user_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.user_settings_service.upsert_user_llm_settings",
            return_value=record,
        ) as upsert_settings, patch(
            "app.services.user_settings_service._list_available_models",
            return_value=["deepseek-v4-flash"],
        ), patch(
            "app.services.user_settings_service.create_openai_compatible_chat_model",
        ) as create_model:
            result = test_user_llm_settings(
                1,
                {
                    "credential_mode": "user",
                    "provider": "deepseek",
                    "api_key": "new-plain-key",
                },
            )

        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(persisted_settings["model"], "")
        self.assertEqual(result["models"], ["deepseek-v4-flash"])
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
