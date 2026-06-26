import os
from typing import List

from langchain_core.embeddings import Embeddings
from zai import ZhipuAiClient


class ZhipuAIEmbeddings(Embeddings):
    """`Zhipuai Embeddings` embedding models."""

    def __init__(self):
        """
        实例化ZhipuAI客户端。

        使用环境变量：ZAI_EMD_API
        """
        self.client = ZhipuAiClient(
            api_key=os.environ.get("ZAI_EMD_API")
        )

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

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = self.client.embeddings.create(
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
