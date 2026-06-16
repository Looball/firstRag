# 导入变量声明
from langchain_core.vectorstores.base import VectorStoreRetriever
from typing import Any
from langchain_core.documents import Document

# 导入Chroma和Zhipu词嵌入模型
from langchain_chroma import Chroma
from app.services.vectors.embedding_model import ZhipuAIEmbeddings


# 创建向量知识库检索器
def get_retriever(
        store_path: str = "./vector_db/chroma",
        **kwargs: Any
) -> VectorStoreRetriever:
    """
    从本地Chroma向量数据库创建检索器。

    使用环境变量：ZAI_EMD_API
    """
    embedding = ZhipuAIEmbeddings()
    vectordb = Chroma(
        persist_directory=store_path,
        embedding_function=embedding,
    )
    return vectordb.as_retriever(**kwargs)


# 提取检索器文本
def get_res_doc(inputs: dict[str, Any]) -> str:
    docs = inputs.get("context", [])
    return "\n\n".join(
        doc.page_content
        for doc in docs
        if isinstance(doc, Document)
    )


