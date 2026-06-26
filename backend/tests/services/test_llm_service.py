"""聊天模型兼容工厂的单元测试。"""

import unittest
from unittest.mock import patch

from app.services.llm_service import (
    ChatModelSettings,
    build_system_chat_model_settings,
    create_openai_compatible_chat_model,
    resolve_base_url,
)


class ChatModelFactoryTests(unittest.TestCase):
    """验证国内厂商预设和通用配置校验。"""

    def test_deepseek_uses_preset_base_url(self) -> None:
        """DeepSeek 未单独配置地址时应使用其兼容接口预设。"""
        settings = ChatModelSettings(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key="test-key",
            base_url=None,
            temperature=0.2,
            max_tokens=8000,
            timeout_seconds=60,
            max_retries=2,
        )

        model = create_openai_compatible_chat_model(settings)

        self.assertEqual(model.model_name, "deepseek-v4-flash")
        self.assertEqual(model.openai_api_base, "https://api.deepseek.com/v1")
        self.assertTrue(model.streaming)

    def test_custom_provider_requires_base_url(self) -> None:
        """自定义兼容厂商缺少地址时应拒绝创建模型。"""
        with self.assertRaisesRegex(ValueError, "LLM_BASE_URL"):
            resolve_base_url("openai_compatible", None)

    def test_custom_provider_accepts_configured_base_url(self) -> None:
        """自定义兼容厂商应使用显式配置的服务地址。"""
        self.assertEqual(
            resolve_base_url(
                "openai_compatible",
                "https://llm.example.com/v1/",
            ),
            "https://llm.example.com/v1",
        )

    def test_legacy_deepseek_api_key_is_used_as_fallback(self) -> None:
        """未配置新变量时应兼容旧 DeepSeek 默认配置。"""
        with patch("app.services.llm_service.config.LLM_PROVIDER", "deepseek"), patch(
            "app.services.llm_service.config.LLM_MODEL",
            None,
        ), patch(
            "app.services.llm_service.config.LLM_API_KEY",
            "legacy-key",
        ):
            settings = build_system_chat_model_settings()

        self.assertEqual(settings.model, "deepseek-v4-flash")
        self.assertEqual(settings.api_key, "legacy-key")


if __name__ == "__main__":
    unittest.main()
