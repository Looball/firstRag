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

from app.services.vectors.embedding_model import ZhipuAIEmbeddings


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


if __name__ == "__main__":
    unittest.main()
