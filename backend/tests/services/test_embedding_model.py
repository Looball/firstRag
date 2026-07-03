"""Embedding 模型配置行为测试。"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.vectors.embedding_model import (
    DashScopeQwenEmbeddings,
    ZhipuAIEmbeddings,
    create_embedding_model,
    get_embedding_cache_identity,
)
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
)


def build_embedding_settings(
    provider: str = "qwen",
    model: str = "text-embedding-v4",
    api_key: str = "user-api-key",
    base_url: str | None = None,
    dimensions: int | None = None,
) -> EmbeddingModelSettings:
    """构造用户级 embedding 设置。"""
    return EmbeddingModelSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        dimensions=dimensions,
        timeout_seconds=60,
        max_retries=2,
    )


class ZhipuAIEmbeddingsTests(unittest.TestCase):
    """验证智谱 embedding 使用用户配置。"""

    def test_constructor_does_not_require_api_key(self) -> None:
        """构造对象不应立刻创建外部客户端。"""
        embeddings = ZhipuAIEmbeddings(
            build_embedding_settings(
                provider="zhipuai",
                model="embedding-3",
                api_key="",
            )
        )

        self.assertIsNone(embeddings.client)

    def test_embed_documents_requires_api_key_at_call_time(self) -> None:
        """真正生成 embedding 时才要求当前用户保存 Key。"""
        embeddings = ZhipuAIEmbeddings(
            build_embedding_settings(
                provider="zhipuai",
                model="embedding-3",
                api_key="",
            )
        )

        with self.assertRaisesRegex(RuntimeError, "当前用户"):
            embeddings.embed_documents(["hello"])

    def test_embed_documents_uses_configured_api_key(self) -> None:
        """配置用户 Key 后应创建智谱客户端并返回向量。"""
        response = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
        )

        with patch(
            "app.services.vectors.embedding_model.ZhipuAiClient",
        ) as client_cls:
            client_cls.return_value.embeddings.create.return_value = response

            embeddings = ZhipuAIEmbeddings(
                build_embedding_settings(
                    provider="zhipuai",
                    model="embedding-3",
                    api_key="zhipu-test-key",
                )
            )
            result = embeddings.embed_documents(["hello"])

        self.assertEqual(result, [[0.1, 0.2, 0.3]])
        client_cls.assert_called_once_with(api_key="zhipu-test-key")
        client_cls.return_value.embeddings.create.assert_called_once_with(
            model="embedding-3",
            input=["hello"],
        )


class DashScopeQwenEmbeddingsTests(unittest.TestCase):
    """验证阿里云 Qwen embedding provider 的配置和请求体。"""

    def test_constructor_does_not_require_api_key(self) -> None:
        """构造对象不应立刻创建 OpenAI client。"""
        embeddings = DashScopeQwenEmbeddings(
            build_embedding_settings(api_key="")
        )

        self.assertIsNone(embeddings.client)
        self.assertEqual(embeddings.model, "text-embedding-v4")

    def test_embed_documents_uses_openai_compatible_embeddings(self) -> None:
        """Qwen embedding 应调用阿里 OpenAI-compatible embeddings API。"""
        response = SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[0.1, 0.2]),
                SimpleNamespace(embedding=[0.3, 0.4]),
            ],
        )

        with patch(
            "app.services.vectors.embedding_model.OpenAI",
        ) as client_cls:
            client_cls.return_value.embeddings.create.return_value = response

            embeddings = DashScopeQwenEmbeddings(
                build_embedding_settings(
                    api_key="dashscope-test-key",
                    dimensions=1024,
                )
            )
            result = embeddings.embed_documents(["hello", "world"])

        self.assertEqual(result, [[0.1, 0.2], [0.3, 0.4]])
        client_cls.assert_called_once_with(
            api_key="dashscope-test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=60,
            max_retries=2,
        )
        client_cls.return_value.embeddings.create.assert_called_once_with(
            model="text-embedding-v4",
            input=["hello", "world"],
            dimensions=1024,
        )

    def test_embedding_factory_uses_qwen_provider(self) -> None:
        """用户向量设置为 qwen 时应创建 Qwen embedding provider。"""
        settings = build_embedding_settings()
        with patch(
            "app.services.vectors.embedding_model.get_effective_embedding_model_settings",
            return_value=settings,
        ):
            embeddings = create_embedding_model(1)
            cache_identity = get_embedding_cache_identity(1)

        self.assertIsInstance(embeddings, DashScopeQwenEmbeddings)
        self.assertEqual(cache_identity, ("1", "qwen", "text-embedding-v4", ""))


if __name__ == "__main__":
    unittest.main()
