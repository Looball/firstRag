from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import production_preflight


VALID_FERNET_KEY = "u_JVnB0dF3XnZomZbGLifxOqHQS9MzvP6Z2B9mF6dxo="


class ProductionPreflightScriptTests(unittest.TestCase):
    """生产 preflight 脚本测试。"""

    def test_load_env_file_reads_simple_dotenv_without_shell_execution(self) -> None:
        """dotenv 解析只读取 KEY=VALUE 行。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "# ignored",
                        "POSTGRES_PASSWORD='secret-value'",
                        "INVALID KEY=value",
                        "JWT_SECRET_KEY=plain-secret",
                    ]
                ),
                encoding="utf-8",
            )

            values = production_preflight.load_env_file(env_file)

        self.assertEqual(values["POSTGRES_PASSWORD"], "secret-value")
        self.assertEqual(values["JWT_SECRET_KEY"], "plain-secret")
        self.assertNotIn("INVALID KEY", values)

    def test_validate_secret_settings_rejects_placeholders(self) -> None:
        """生产 secret 不能沿用模板占位值。"""
        errors = production_preflight.validate_secret_settings(
            {
                "POSTGRES_PASSWORD": "replace-with-a-strong-postgres-password",
                "JWT_SECRET_KEY": "replace-with-a-random-secret",
                "USER_SETTINGS_ENCRYPTION_KEY": "replace-with-a-fernet-key",
            }
        )

        self.assertGreaterEqual(len(errors), 3)
        self.assertTrue(any("POSTGRES_PASSWORD" in error for error in errors))

    def test_validate_secret_settings_accepts_realistic_values(self) -> None:
        """格式正确的生产配置不应报 secret 错误。"""
        errors = production_preflight.validate_secret_settings(
            {
                "POSTGRES_PASSWORD": "a-very-long-random-password",
                "JWT_SECRET_KEY": "jwt-secret-with-at-least-thirty-two-chars",
                "USER_SETTINGS_ENCRYPTION_KEY": VALID_FERNET_KEY,
            }
        )

        self.assertEqual(errors, [])

    def test_optional_provider_settings_allow_missing_keys(self) -> None:
        """Provider Key 可后配置，默认不应阻塞 preflight。"""
        errors = production_preflight.validate_optional_provider_settings({})

        self.assertEqual(errors, [])

    def test_optional_provider_settings_reject_rerank_placeholders(self) -> None:
        """已填写的远程 rerank Key 不能仍是模板占位值。"""
        errors = production_preflight.validate_optional_provider_settings(
            {
                "RERANK_API_KEY": "replace-with-your-rerank-api-key",
            }
        )

        self.assertEqual(len(errors), 1)
        self.assertTrue(any("RERANK_API_KEY" in error for error in errors))

    def test_optional_provider_settings_can_require_keys(self) -> None:
        """未启用远程 rerank 时不要求 provider Key。"""
        missing_errors = production_preflight.validate_optional_provider_settings(
            {},
            require_provider_keys=True,
        )
        configured_errors = production_preflight.validate_optional_provider_settings(
            {
                "RERANK_PROVIDER": "local",
            },
            require_provider_keys=True,
        )

        self.assertEqual(missing_errors, [])
        self.assertEqual(configured_errors, [])

    def test_optional_provider_settings_support_user_configured_embedding(self) -> None:
        """embedding Key 已迁移到用户设置，不再由 preflight 检查。"""
        errors = production_preflight.validate_optional_provider_settings(
            {},
            require_provider_keys=True,
        )

        self.assertEqual(errors, [])

    def test_optional_provider_settings_requires_qwen_rerank_base_url(self) -> None:
        """公开 smoke test 前启用 Qwen rerank 时应要求工作空间地址。"""
        errors = production_preflight.validate_optional_provider_settings(
            {
                "RERANK_PROVIDER": "qwen",
            },
            require_provider_keys=True,
        )

        self.assertTrue(any("RERANK_BASE_URL" in error for error in errors))

    def test_validate_port_bindings_requires_loopback(self) -> None:
        """生产 compose 端口应只绑定本机地址。"""
        errors = production_preflight.validate_port_bindings(
            {
                "FRONTEND_PORT": "3000",
                "BACKEND_PORT": "0.0.0.0:8000",
                "POSTGRES_PORT": "127.0.0.1:5432",
            }
        )

        self.assertEqual(len(errors), 2)
        self.assertTrue(any("FRONTEND_PORT" in error for error in errors))
        self.assertTrue(any("BACKEND_PORT" in error for error in errors))

    def test_validate_redis_settings_accepts_compose_defaults(self) -> None:
        """Compose 内置 Redis 默认配置应通过生产 Redis 检查。"""
        errors = production_preflight.validate_redis_settings(
            {
                "REDIS_ENABLED": "true",
                "REDIS_URL": "redis://redis:6379/0",
                "RATE_LIMIT_BACKEND": "redis",
                "RATE_LIMIT_REDIS_FAILURE_MODE": "fail_closed",
            }
        )

        self.assertEqual(errors, [])

    def test_validate_redis_settings_rejects_external_url_without_auth(self) -> None:
        """外部 Redis 连接串必须带认证信息。"""
        errors = production_preflight.validate_redis_settings(
            {
                "REDIS_ENABLED": "true",
                "REDIS_URL": "redis://cache.example.com:6379/0",
                "RATE_LIMIT_BACKEND": "redis",
                "RATE_LIMIT_REDIS_FAILURE_MODE": "fail_closed",
            }
        )

        self.assertTrue(any("REDIS_URL" in error for error in errors))
        self.assertTrue(any("认证" in error for error in errors))

    def test_validate_redis_settings_rejects_default_password_without_leaking(self) -> None:
        """Redis 默认密码应失败，错误信息不能泄露连接串密码。"""
        errors = production_preflight.validate_redis_settings(
            {
                "REDIS_ENABLED": "true",
                "REDIS_URL": "redis://default:password@cache.example.com:6379/0",
                "RATE_LIMIT_BACKEND": "redis",
                "RATE_LIMIT_REDIS_FAILURE_MODE": "fail_closed",
            }
        )

        joined_errors = "\n".join(errors)
        self.assertTrue(any("Redis 密码" in error for error in errors))
        self.assertNotIn("password@cache.example.com", joined_errors)
        self.assertNotIn("redis://", joined_errors)

    def test_validate_redis_settings_rejects_fail_open_rate_limit(self) -> None:
        """生产 Redis 限流不能配置 fail-open。"""
        errors = production_preflight.validate_redis_settings(
            {
                "REDIS_ENABLED": "true",
                "REDIS_URL": "redis://redis:6379/0",
                "RATE_LIMIT_BACKEND": "redis",
                "RATE_LIMIT_REDIS_FAILURE_MODE": "fail_open",
            }
        )

        self.assertTrue(any("fail_closed" in error for error in errors))

    def test_validate_compose_redis_service_requires_healthcheck_and_private_port(self) -> None:
        """Compose Redis service 不能暴露 ports，且必须有 healthcheck。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text(
                "\n".join(
                    [
                        "services:",
                        "  redis:",
                        "    image: redis:7-alpine",
                        "    ports:",
                        "      - \"6379:6379\"",
                        "  backend:",
                        "    image: backend",
                    ]
                ),
                encoding="utf-8",
            )

            errors = production_preflight.validate_compose_redis_service(
                compose_file,
            )

        self.assertTrue(any("ports" in error for error in errors))
        self.assertTrue(any("healthcheck" in error for error in errors))

    def test_validate_runtime_paths_checks_required_directories(self) -> None:
        """持久化目录和模型目录缺失时应失败。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uploads = root / "uploads"
            vector_db = root / "vector_db"
            models = root / "models"
            uploads.mkdir()
            vector_db.mkdir()
            models.mkdir()

            errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "VECTOR_DB_DIR": os.fspath(vector_db),
                    "MODELS_DIR": os.fspath(models),
                }
            )
            reranker_errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "VECTOR_DB_DIR": os.fspath(vector_db),
                    "MODELS_DIR": os.fspath(models),
                },
                require_reranker=True,
            )

            (models / "rerankers/bge-reranker-base").mkdir(parents=True)
            fixed_errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "VECTOR_DB_DIR": os.fspath(vector_db),
                    "MODELS_DIR": os.fspath(models),
                }
            )

        self.assertEqual(errors, [])
        self.assertTrue(any("reranker" in error for error in reranker_errors))
        self.assertEqual(fixed_errors, [])


if __name__ == "__main__":
    unittest.main()
