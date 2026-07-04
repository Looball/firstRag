"""用户 rerank 模型设置服务的单元测试。"""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.services.rerank_settings_service import (
    check_user_rerank_settings,
    get_effective_rerank_model_settings,
    get_serialized_user_rerank_providers,
    update_user_rerank_settings,
)


def build_rerank_record() -> dict:
    """构造一份用户 rerank 模型数据库记录。"""
    return {
        "user_id": 1,
        "provider": "voyage",
        "model": "rerank-2.5",
        "base_url": None,
        "instruct": None,
        "api_key_ciphertext": "encrypted-key",
        "api_key_hint": "••••-key",
        "encryption_key_version": 1,
        "timeout_seconds": Decimal("60.00"),
        "max_retries": 2,
    }


class UserRerankSettingsServiceTests(unittest.TestCase):
    """验证用户 rerank 模型设置的密钥保护与更新规则。"""

    def setUp(self) -> None:
        """默认隔离 rerank 厂商凭据仓库，避免单元测试连接真实数据库。"""
        self.get_provider_credential = patch(
            "app.services.rerank_settings_service.get_user_rerank_provider_credential",
            return_value=None,
        )
        self.get_provider_credentials = patch(
            "app.services.rerank_settings_service.get_user_rerank_provider_credentials",
            return_value=[],
        )
        self.upsert_provider_credential = patch(
            "app.services.rerank_settings_service.upsert_user_rerank_provider_credential",
            return_value=build_rerank_record(),
        )
        self.get_provider_credential.start()
        self.get_provider_credentials.start()
        self.upsert_provider_credential.start()
        self.addCleanup(self.get_provider_credential.stop)
        self.addCleanup(self.get_provider_credentials.stop)
        self.addCleanup(self.upsert_provider_credential.stop)

    def test_missing_settings_defaults_to_local_without_api_key(self) -> None:
        """未配置用户 rerank 时默认使用本地 provider，且不要求 API Key。"""
        with patch(
            "app.services.rerank_settings_service.get_user_rerank_settings",
            return_value=None,
        ):
            settings = get_effective_rerank_model_settings(1)

        self.assertEqual(settings.provider, "local")
        self.assertEqual(settings.api_key, "")

    def test_provider_catalog_marks_saved_remote_credentials(self) -> None:
        """rerank 厂商目录应返回远程厂商凭据状态。"""
        with patch(
            "app.services.rerank_settings_service.get_user_rerank_provider_credentials",
            return_value=[
                {
                    "provider": "voyage",
                    "api_key_hint": "••••abcd",
                }
            ],
        ):
            providers = get_serialized_user_rerank_providers(1)

        local = next(item for item in providers if item["id"] == "local")
        voyage = next(item for item in providers if item["id"] == "voyage")
        self.assertTrue(local["has_api_key"])
        self.assertTrue(voyage["has_api_key"])
        self.assertEqual(voyage["api_key_hint"], "••••abcd")

    def test_update_remote_rerank_settings_encrypts_api_key(self) -> None:
        """新提交的 rerank API Key 应加密后保存到厂商凭据表。"""
        saved_record = build_rerank_record()
        with patch(
            "app.services.rerank_settings_service.get_user_rerank_settings",
            side_effect=[None, saved_record],
        ), patch(
            "app.services.rerank_settings_service.encrypt_secret",
            return_value="encrypted-key",
        ) as encrypt_secret, patch(
            "app.services.rerank_settings_service.upsert_user_rerank_settings",
            return_value=saved_record,
        ) as upsert_settings:
            settings = update_user_rerank_settings(
                1,
                {
                    "provider": "voyage",
                    "model": "rerank-2.5",
                    "api_key": "plain-key",
                },
            )

        encrypt_secret.assert_called_once_with("plain-key")
        persisted_settings = upsert_settings.call_args.args[1]
        self.assertEqual(
            persisted_settings["api_key_ciphertext"],
            "encrypted-key",
        )
        self.assertEqual(settings["provider"], "voyage")

    def test_check_rerank_settings_calls_provider(self) -> None:
        """连接测试应使用用户配置执行一次 rerank。"""
        fake_reranker = MagicMock()
        fake_reranker.rerank.return_value = [
            Document(page_content="ok", metadata={"rerank_score": 0.9}),
        ]
        with patch(
            "app.services.rerank_settings_service.get_user_rerank_settings",
            return_value=build_rerank_record(),
        ), patch(
            "app.services.rerank_settings_service.get_user_rerank_provider_credential",
            return_value={
                "provider": "voyage",
                "api_key_ciphertext": "encrypted-key",
                "api_key_hint": "••••-key",
                "encryption_key_version": 1,
            },
        ), patch(
            "app.services.rerank_settings_service.decrypt_secret",
            return_value="plain-key",
        ), patch(
            "app.services.retrieval.reranker.create_reranker_from_settings",
            return_value=fake_reranker,
        ) as create_reranker:
            result = check_user_rerank_settings(1, {})

        self.assertEqual(result["top_score"], 0.9)
        settings = create_reranker.call_args.args[0]
        self.assertEqual(settings.api_key, "plain-key")
        fake_reranker.rerank.assert_called_once()


if __name__ == "__main__":
    unittest.main()
