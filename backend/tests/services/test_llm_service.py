"""聊天模型兼容工厂的单元测试。"""

import unittest

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

    def test_default_settings_do_not_include_environment_api_key(self) -> None:
        """设置页默认值不应携带服务器环境变量中的 provider Key。"""
        settings = build_system_chat_model_settings()
        self.assertEqual(settings.model, "deepseek-v4-flash")
        self.assertEqual(settings.api_key, "")

    def test_chat_model_requires_user_api_key(self) -> None:
        """真正创建模型时必须提供当前用户保存的 API Key。"""
        settings = build_system_chat_model_settings()

        with self.assertRaisesRegex(ValueError, "当前用户"):
            create_openai_compatible_chat_model(settings)


if __name__ == "__main__":
    unittest.main()
