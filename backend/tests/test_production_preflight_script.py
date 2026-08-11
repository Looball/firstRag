from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


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

    def test_validate_milvus_settings_accepts_secure_compose_values(self) -> None:
        """Milvus 内网 URI、强 token、MinIO secret 和 Strong 应通过。"""
        errors = production_preflight.validate_milvus_settings(
            {
                "MILVUS_URI": "http://milvus-standalone:19530",
                "MILVUS_TOKEN": "root:a-strong-runtime-password",
                "MILVUS_DATABASE": "default",
                "MILVUS_COLLECTION_PREFIX": "firstrag",
                "MILVUS_TIMEOUT_SECONDS": "10",
                "MILVUS_CONSISTENCY_LEVEL": "Strong",
                "MILVUS_MINIO_ACCESS_KEY": "firstrag-production",
                "MILVUS_MINIO_SECRET_KEY": "a-strong-minio-secret-key",
            }
        )

        self.assertEqual(errors, [])

    def test_validate_milvus_settings_rejects_unsafe_values_without_leak(self) -> None:
        """Loopback、弱 token、非法命名和非 Strong 配置应失败且不泄露 token。"""
        token = "root:short"
        errors = production_preflight.validate_milvus_settings(
            {
                "MILVUS_URI": "http://localhost:19530/path",
                "MILVUS_TOKEN": f"reader:{token.split(':', 1)[1]}$",
                "MILVUS_DATABASE": "bad-name",
                "MILVUS_COLLECTION_PREFIX": "Bad-Prefix",
                "MILVUS_TIMEOUT_SECONDS": "0",
                "MILVUS_CONSISTENCY_LEVEL": "Bounded",
            }
        )

        joined_errors = "\n".join(errors)
        self.assertIn("loopback", joined_errors)
        self.assertIn("MILVUS_TOKEN", joined_errors)
        self.assertIn("Strong", joined_errors)
        self.assertNotIn(token.split(":", 1)[1], joined_errors)

    def test_validate_milvus_settings_matches_compose_bootstrap_contract(self) -> None:
        """内置 Milvus 只接受 root 和 entrypoint 安全字符集。"""
        errors = production_preflight.validate_milvus_settings(
            {
                "MILVUS_URI": "http://milvus-standalone:19530",
                "MILVUS_TOKEN": "reader:strong-password$",
                "MILVUS_DATABASE": "default",
                "MILVUS_COLLECTION_PREFIX": "firstrag",
                "MILVUS_TIMEOUT_SECONDS": "10",
                "MILVUS_CONSISTENCY_LEVEL": "Strong",
                "MILVUS_MINIO_ACCESS_KEY": "firstrag-production",
                "MILVUS_MINIO_SECRET_KEY": "a-strong-minio-secret-key",
            }
        )

        joined_errors = "\n".join(errors)
        self.assertIn("bootstrap password", joined_errors)
        self.assertIn("root", joined_errors)
        self.assertNotIn("strong-password$", joined_errors)

    def test_validate_vector_store_settings_requires_milvus_auth(self) -> None:
        """唯一 vector store 配置必须通过 Milvus 强认证门禁。"""
        default_errors = production_preflight.validate_vector_store_settings({})
        self.assertTrue(any("MILVUS" in error for error in default_errors))

    def test_validate_compose_milvus_services_accepts_repository_topology(self) -> None:
        """仓库默认 Milvus 应满足固定版本、内网和认证门禁。"""
        errors = production_preflight.validate_compose_milvus_services()

        self.assertEqual(errors, [])

    def test_validate_compose_milvus_services_rejects_public_unpinned_runtime(self) -> None:
        """latest、host ports、缺失持久化与 probe 必须失败。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text(
                "\n".join(
                    [
                        "services:",
                        "  milvus-etcd:",
                        "    image: quay.io/coreos/etcd:latest",
                        "  milvus-minio:",
                        "    image: minio/minio:latest",
                        "  milvus-standalone:",
                        "    image: milvusdb/milvus:latest",
                        "    ports:",
                        "      - \"19530:19530\"",
                        "  backend:",
                        "    image: backend",
                        "  worker:",
                        "    image: backend",
                    ]
                ),
                encoding="utf-8",
            )

            errors = production_preflight.validate_compose_milvus_services(
                compose_file
            )

        joined_errors = "\n".join(errors)
        self.assertIn("milvusdb/milvus:v3.0.0", joined_errors)
        self.assertIn("host ports", joined_errors)
        self.assertIn("volume", joined_errors)
        self.assertIn("milvus-health-probe", joined_errors)

    def test_validate_sparse_encoder_settings_rejects_fixture_and_drift(self) -> None:
        """生产环境不能使用 fixture、漂移 revision 或 CPU FP16。"""
        errors = production_preflight.validate_sparse_encoder_settings(
            {
                "SPARSE_ENCODER_MODE": "fixture",
                "SPARSE_ENCODER_MODEL": "another/model",
                "SPARSE_ENCODER_REVISION": "main",
                "SPARSE_ENCODER_DEVICE": "cpu",
                "SPARSE_ENCODER_USE_FP16": "true",
            }
        )

        joined_errors = "\n".join(errors)
        self.assertIn("禁止 fixture", joined_errors)
        self.assertIn("BAAI/bge-m3", joined_errors)
        self.assertIn("SPARSE_ENCODER_REVISION", joined_errors)
        self.assertIn("FP16", joined_errors)

    def test_validate_sparse_encoder_settings_accepts_fixed_cpu_runtime(self) -> None:
        """固定 BGE-M3 CPU 配置应通过 production 门禁。"""
        errors = production_preflight.validate_sparse_encoder_settings({})

        self.assertEqual(errors, [])

    def test_validate_sparse_encoder_rejects_oversized_client_batch(self) -> None:
        """worker client batch 不得超过 encoder service contract 上限。"""
        errors = production_preflight.validate_sparse_encoder_settings({
            "SPARSE_ENCODER_CLIENT_BATCH_SIZE": "17",
            "SPARSE_ENCODER_MAX_BATCH_SIZE": "16",
        })

        self.assertTrue(any(
            "CLIENT_BATCH_SIZE" in error and "MAX_BATCH_SIZE" in error
            for error in errors
        ))

    def test_validate_compose_sparse_encoder_accepts_repository_topology(self) -> None:
        """仓库拓扑必须是内网单实例并被 backend/worker 共用。"""
        errors = production_preflight.validate_compose_sparse_encoder_service()

        self.assertEqual(errors, [])

    def test_validate_compose_sparse_encoder_rejects_public_fixture(self) -> None:
        """host port、fixture target、缺失缓存和 consumers gate 必须失败。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text(
                "\n".join(
                    [
                        "services:",
                        "  sparse-encoder:",
                        "    build:",
                        "      target: fixture",
                        "    ports:",
                        '      - "8090:8090"',
                        "  backend:",
                        "    image: backend",
                        "  worker:",
                        "    image: backend",
                    ]
                ),
                encoding="utf-8",
            )

            errors = production_preflight.validate_compose_sparse_encoder_service(
                compose_file
            )

        joined_errors = "\n".join(errors)
        self.assertIn("target: runtime", joined_errors)
        self.assertIn("host ports", joined_errors)
        self.assertIn("bge_m3_cache", joined_errors)
        self.assertIn("backend", joined_errors)

    def test_parse_compose_ps_records_supports_object_and_json_lines(self) -> None:
        """runtime health 兼容 Compose 的单对象和逐行 JSON 输出。"""
        object_records = production_preflight.parse_compose_ps_records(
            '{"Service":"milvus-standalone","State":"running","Health":"healthy"}'
        )
        line_records = production_preflight.parse_compose_ps_records(
            "\n".join(
                [
                    '{"Service":"milvus-standalone","State":"running","Health":"healthy"}',
                    '{"Service":"backend","State":"running","Health":""}',
                ]
            )
        )

        self.assertEqual(len(object_records), 1)
        self.assertEqual(len(line_records), 2)

    def test_run_milvus_runtime_health_check_requires_container_and_two_probes(self) -> None:
        """Milvus runtime 必须 healthy，且 backend/worker probe 均成功。"""
        completed = CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"Service":"milvus-standalone","State":"running","Health":"healthy"}\n',
            stderr="",
        )
        probe = CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with patch.object(
            production_preflight.subprocess,
            "run",
            side_effect=[completed, probe, probe],
        ) as run_mock:
            result = production_preflight.run_milvus_runtime_health_check({})

        self.assertTrue(result.success)
        self.assertEqual(run_mock.call_count, 3)

    def test_run_milvus_resource_check_warns_below_recommended_memory(self) -> None:
        """满足最低但低于 16 GiB 时应成功并给出 warning。"""
        docker_info = CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"NCPU":8,"MemTotal":16484397056}\n',
            stderr="",
        )
        with patch.object(
            production_preflight.subprocess,
            "run",
            return_value=docker_info,
        ):
            result = production_preflight.run_milvus_resource_check({})

        self.assertTrue(result.success)
        self.assertIn("warning", result.message)

    def test_validate_runtime_paths_checks_persistent_directories(self) -> None:
        """Milvus runtime 只要求 uploads、models 与可选 reranker 目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            uploads = root / "uploads"
            models = root / "models"
            uploads.mkdir()
            models.mkdir()

            errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "MODELS_DIR": os.fspath(models),
                }
            )
            reranker_errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "MODELS_DIR": os.fspath(models),
                },
                require_reranker=True,
            )

            (models / "rerankers/bge-reranker-base").mkdir(parents=True)
            fixed_errors = production_preflight.validate_runtime_paths(
                {
                    "UPLOADS_DIR": os.fspath(uploads),
                    "MODELS_DIR": os.fspath(models),
                }
            )

        self.assertEqual(errors, [])
        self.assertTrue(any("reranker" in error for error in reranker_errors))
        self.assertEqual(fixed_errors, [])


if __name__ == "__main__":
    unittest.main()
