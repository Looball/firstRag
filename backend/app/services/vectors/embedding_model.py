from __future__ import annotations

import os
from typing import List

from langchain_core.embeddings import Embeddings
from zai import ZhipuAiClient


class ZhipuAIEmbeddings(Embeddings):
    """`Zhipuai Embeddings` embedding models."""

    def __init__(self):
        """
        初始化 embedding 包装器，客户端在实际调用时再创建。

        使用环境变量：ZAI_EMD_API
        """
        self.client: ZhipuAiClient | None = None

    def _get_client(self) -> ZhipuAiClient:
        """按需创建智谱客户端，避免缺少 Key 时影响服务启动。"""
        api_key = (os.environ.get("ZAI_EMD_API") or "").strip()
        if not api_key or api_key.startswith("replace-with-"):
            raise RuntimeError(
                "缺少环境变量 ZAI_EMD_API，请配置后重启 backend/worker 再执行向量化。"
            )
        if self.client is None:
            self.client = ZhipuAiClient(api_key=api_key)
        return self.client

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        生成输入文本列表的embedding。

        Args:
            texts: 要生成embedding的文本列表。

        Returns:
            输入列表中每个文档的embedding列表。
        """
        batch_size = 64  # 智谱AI embedding一次最多接收64条
        all_embeddings = []
        client = self._get_client()

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = client.embeddings.create(
                model="embedding-3",
                input=batch_texts,
            )
            all_embeddings.extend(
                item.embedding for item in response.data
            )

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        生成输入文本的embedding。

        Args:
            text: 要生成embedding的文本。

        Returns:
            输入文本的embedding。
        """
        return self.embed_documents([text])[0]
