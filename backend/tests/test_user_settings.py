"""用户聊天模型设置接口的回归测试。"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.core.security import get_current_user_id
from app.main import app


class UserLLMSettingsApiTests(unittest.TestCase):
    """验证设置接口的认证用户传递和响应边界。"""

    def setUp(self) -> None:
        """为每个测试注入固定的认证用户。"""
        reset_rate_limits()
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由测试。"""
        app.dependency_overrides.clear()
        self.client.close()
        reset_rate_limits()

    def test_get_settings_returns_sanitized_settings(self) -> None:
        """读取设置接口只能返回已脱敏的模型配置。"""
        settings = {
            "credential_mode": "user",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com/v1",
            "has_api_key": True,
            "api_key_hint": "••••abcd",
            "temperature": 0.2,
            "max_tokens": 8000,
            "timeout_seconds": 60.0,
            "max_retries": 2,
        }
        with patch(
            "app.api.user_settings.get_serialized_user_llm_settings",
            return_value=settings,
        ):
            response = self.client.get("/user/settings")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertNotIn("api_key", response.json()["settings"])
        self.assertEqual(
            response.json()["settings"]["api_key_hint"],
            "••••abcd",
        )

    def test_get_providers_returns_backend_catalog(self) -> None:
        """厂商选项应由后端统一提供，前端无需维护硬编码清单。"""
        providers = [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "requires_base_url": False,
                "enabled": True,
            }
        ]
        with patch(
            "app.api.user_settings.get_serialized_user_llm_providers",
            return_value=providers,
        ):
            response = self.client.get("/user/settings/providers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "providers": providers},
        )

    def test_get_provider_models_uses_saved_credential(self) -> None:
        """厂商模型列表接口应通过该厂商的已保存凭据读取。"""
        with patch(
            "app.api.user_settings.get_saved_provider_models",
            return_value=["qwen-plus"],
        ) as get_models:
            response = self.client.post("/user/settings/providers/qwen/models")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "provider": "qwen", "models": ["qwen-plus"]},
        )
        get_models.assert_called_once_with(1, "qwen")

    def test_test_settings_without_body_uses_saved_settings(self) -> None:
        """空请求体应测试已保存设置，而不是要求重复提交 API Key。"""
        with patch(
            "app.api.user_settings.check_user_llm_settings",
            return_value={
                "message": "模型连接测试成功",
                "models": ["deepseek-v4-flash"],
                "model_list_available": True,
                "api_key_saved": False,
            },
        ) as test_settings:
            response = self.client.post("/user/settings/test")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["models"],
            ["deepseek-v4-flash"],
        )
        test_settings.assert_called_once_with(1, {})

    def test_test_settings_is_rate_limited(self) -> None:
        """模型测试接口高频调用应返回 429 并停止访问 provider。"""
        with patch(
            "app.api.user_settings.MODEL_TEST_RATE_LIMIT_MAX_REQUESTS",
            1,
        ), patch(
            "app.api.user_settings.API_RATE_LIMIT_WINDOW_SECONDS",
            60,
        ), patch(
            "app.api.user_settings.check_user_llm_settings",
            return_value={
                "message": "模型连接测试成功",
                "models": [],
                "model_list_available": False,
                "api_key_saved": False,
            },
        ) as test_settings:
            first = self.client.post("/user/settings/test")
            second = self.client.post("/user/settings/test")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(
            second.json(),
            {"detail": "模型配置测试过于频繁，请稍后再试。"},
        )
        self.assertIn("retry-after", second.headers)
        test_settings.assert_called_once()

    def test_test_settings_redacts_submitted_api_key_in_error(self) -> None:
        """模型测试错误不应回显用户本次提交的 API Key。"""
        submitted_api_key = "test-user-key-value"
        with patch(
            "app.api.user_settings.check_user_llm_settings",
            side_effect=ValueError(
                f"provider rejected api_key={submitted_api_key}",
            ),
        ):
            response = self.client.post(
                "/user/settings/test",
                json={
                    "credential_mode": "user",
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": submitted_api_key,
                },
            )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertNotIn(submitted_api_key, detail)
        self.assertIn("[已脱敏]", detail)


if __name__ == "__main__":
    unittest.main()
