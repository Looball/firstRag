"""认证限流的回归测试。"""

import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.main import app


class LoginRateLimitTests(unittest.TestCase):
    """验证失败登录会被进程内限流保护。"""

    def setUp(self) -> None:
        """为每个测试创建干净的限流状态。"""
        reset_rate_limits()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """关闭测试客户端并清理限流状态。"""
        self.client.close()
        reset_rate_limits()

    def test_failed_login_is_rate_limited_by_username_and_client(self) -> None:
        """同一用户名连续失败超过阈值后应返回 429。"""
        with patch(
            "app.api.auth.LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS",
            2,
        ), patch(
            "app.api.auth.LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS",
            60,
        ), patch(
            "app.api.auth.get_user_by_username",
            return_value=None,
        ) as get_user:
            first = self.client.post(
                "/login",
                json={"username": "alice", "password": "wrong"},
            )
            second = self.client.post(
                "/login",
                json={"username": "alice", "password": "wrong"},
            )
            third = self.client.post(
                "/login",
                json={"username": "alice", "password": "wrong"},
            )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 401)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(
            third.json(),
            {"detail": "登录失败次数过多，请稍后再试。"},
        )
        self.assertIn("retry-after", third.headers)
        self.assertEqual(get_user.call_count, 2)


class PublicRegistrationControlTests(unittest.TestCase):
    """验证公开 demo 注册开关。"""

    def setUp(self) -> None:
        """为每个测试创建干净的限流状态。"""
        reset_rate_limits()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """关闭测试客户端并清理限流状态。"""
        self.client.close()
        reset_rate_limits()

    def test_register_rejects_when_public_registration_disabled(self) -> None:
        """关闭注册时不应创建用户，也不泄露内部配置。"""
        with patch(
            "app.api.auth.ALLOW_PUBLIC_REGISTRATION",
            False,
        ), patch(
            "app.api.auth.create_user_with_default_knowledge_base",
        ) as create_user:
            response = self.client.post(
                "/register",
                json={"username": "alice", "password": "secret"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "当前演示环境暂不开放注册，请使用已提供的账号登录。"},
        )
        self.assertNotIn("ALLOW_PUBLIC_REGISTRATION", response.text)
        create_user.assert_not_called()

    def test_register_allows_when_public_registration_enabled(self) -> None:
        """本地开发默认开启注册时仍能创建新用户。"""
        password_hash = "hashed-password"
        password_hasher = Mock()
        password_hasher.hash.return_value = password_hash
        with patch(
            "app.api.auth.ALLOW_PUBLIC_REGISTRATION",
            True,
        ), patch(
            "app.api.auth.PasswordHash.recommended",
            return_value=password_hasher,
        ), patch(
            "app.api.auth.create_user_with_default_knowledge_base",
            return_value={
                "user_id": 7,
                "username": "alice",
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "默认知识库",
            },
        ) as create_user, patch(
            "app.api.auth.create_access_token",
            return_value="token-7",
        ):
            response = self.client.post(
                "/register",
                json={"username": "alice", "password": "secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "token-7")
        create_user.assert_called_once_with("alice", password_hash)

    def test_login_still_works_when_public_registration_disabled(self) -> None:
        """关闭注册不能影响已有用户登录。"""
        password_hasher = Mock()
        password_hasher.verify.return_value = True
        with patch(
            "app.api.auth.ALLOW_PUBLIC_REGISTRATION",
            False,
        ), patch(
            "app.api.auth.PasswordHash.recommended",
            return_value=password_hasher,
        ), patch(
            "app.api.auth.get_user_by_username",
            return_value={
                "id": 7,
                "username": "alice",
                "password_hash": "hashed-password",
            },
        ), patch(
            "app.api.auth.create_access_token",
            return_value="token-7",
        ):
            response = self.client.post(
                "/login",
                json={"username": "alice", "password": "secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "token-7")


if __name__ == "__main__":
    unittest.main()
