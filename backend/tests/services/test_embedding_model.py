"""Embedding 模型配置行为测试。"""

import os
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


class ZhipuAIEmbeddingsTests(unittest.TestCase):
    """验证 embedding Key 可后配置，不阻塞进程启动。"""

    def test_constructor_does_not_require_api_key(self) -> None:
        """缺少 ZAI_EMD_API 时构造对象不应失败。"""
        with patch.dict(os.environ, {"ZAI_EMD_API": ""}):
            embeddings = ZhipuAIEmbeddings()

        self.assertIsNone(embeddings.client)

    def test_embed_documents_requires_api_key_at_call_time(self) -> None:
        """真正生成 embedding 时才要求 ZAI_EMD_API。"""
        with patch.dict(os.environ, {"ZAI_EMD_API": ""}):
            embeddings = ZhipuAIEmbeddings()

            with self.assertRaisesRegex(RuntimeError, "ZAI_EMD_API"):
                embeddings.embed_documents(["hello"])

    def test_embed_documents_uses_configured_api_key(self) -> None:
        """配置 ZAI_EMD_API 后应创建智谱客户端并返回向量。"""
        response = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
        )

        with patch.dict(os.environ, {"ZAI_EMD_API": "zhipu-test-key"}), patch(
            "app.services.vectors.embedding_model.ZhipuAiClient",
        ) as client_cls:
            client_cls.return_value.embeddings.create.return_value = response

            embeddings = ZhipuAIEmbeddings()
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
        """缺少 DashScope Key 时构造对象不应失败。"""
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "qwen",
                "EMBEDDING_MODEL": "",
                "EMBEDDING_DIMENSIONS": "",
                "DASHSCOPE_API_KEY": "",
            },
        ):
            embeddings = DashScopeQwenEmbeddings()

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

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "qwen",
                "EMBEDDING_MODEL": "text-embedding-v4",
                "EMBEDDING_DIMENSIONS": "1024",
                "DASHSCOPE_API_KEY": "dashscope-test-key",
            },
        ), patch(
            "app.services.vectors.embedding_model.OpenAI",
        ) as client_cls:
            client_cls.return_value.embeddings.create.return_value = response

            embeddings = DashScopeQwenEmbeddings()
            result = embeddings.embed_documents(["hello", "world"])

        self.assertEqual(result, [[0.1, 0.2], [0.3, 0.4]])
        client_cls.assert_called_once_with(
            api_key="dashscope-test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        client_cls.return_value.embeddings.create.assert_called_once_with(
            model="text-embedding-v4",
            input=["hello", "world"],
            dimensions=1024,
        )

    def test_embedding_factory_uses_qwen_provider(self) -> None:
        """EMBEDDING_PROVIDER=qwen 时应创建 Qwen embedding provider。"""
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "qwen", "EMBEDDING_MODEL": "text-embedding-v4"},
        ):
            embeddings = create_embedding_model()
            cache_identity = get_embedding_cache_identity()

        self.assertIsInstance(embeddings, DashScopeQwenEmbeddings)
        self.assertEqual(cache_identity, ("qwen", "text-embedding-v4"))


if __name__ == "__main__":
    unittest.main()
