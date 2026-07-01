"""认证限流的回归测试。"""

import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
