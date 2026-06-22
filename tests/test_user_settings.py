"""用户聊天模型设置接口的回归测试。"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class UserLLMSettingsApiTests(unittest.TestCase):
    """验证设置接口的认证用户传递和响应边界。"""

    def setUp(self) -> None:
        """为每个测试注入固定的认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由测试。"""
        app.dependency_overrides.clear()
        self.client.close()

    def test_get_settings_returns_sanitized_settings(self) -> None:
        """读取设置接口只能返回已脱敏的模型配置。"""
        settings = {
            "credential_mode": "user",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com/v1",
            "has_api_key": True,
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

    def test_test_settings_without_body_uses_saved_settings(self) -> None:
        """空请求体应测试已保存设置，而不是要求重复提交 API Key。"""
        with patch(
            "app.api.user_settings.test_user_llm_settings",
        ) as test_settings:
            response = self.client.post("/user/settings/test")

        self.assertEqual(response.status_code, 200)
        test_settings.assert_called_once_with(1, {})


if __name__ == "__main__":
    unittest.main()
