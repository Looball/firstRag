import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.embedding_service import ZhipuAIEmbeddings


def get_document_paths(folder_path: str | Path = "./local_doc") -> list[Path]:
    """获取本地知识库中的PDF和Markdown文件路径。"""
    supported_extensions = {".pdf", ".md"}
    document_paths = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() in supported_extensions:
                document_paths.append(file_path)

    return document_paths


def load_documents(file_paths: list[Path]) -> list[Document]:
    """根据文件类型加载本地文档。"""
    documents = []

    for file_path in file_paths:
        if file_path.suffix.lower() == ".pdf":
            loader = PyMuPDFLoader(str(file_path))
        elif file_path.suffix.lower() == ".md":
            loader = UnstructuredMarkdownLoader(str(file_path))
        else:
            continue

        documents.extend(loader.load())

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """使用递归字符文本分割器切分文档。"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    return text_splitter.split_documents(documents)


def build_vector_store(
    folder_path: str | Path = "./local_doc",
    persist_directory: str = "./vector_db/chroma",
) -> Chroma:
    """加载、切分本地文档并写入Chroma向量数据库。"""
    file_paths = get_document_paths(folder_path)
    print([str(path) for path in file_paths[:3]])

    documents = load_documents(file_paths)
    split_docs = split_documents(documents)

    print(split_docs)
    print(f"切分后的文件数量：{len(split_docs)}")
    print(
        "切分后的字符数（可以用来大致评估 token 数）："
        f"{sum(len(doc.page_content) for doc in split_docs)}"
    )

    vectordb = Chroma.from_documents(
        documents=split_docs,
        embedding=ZhipuAIEmbeddings(),
        persist_directory=persist_directory,
    )
    print(f"向量库中存储的数量：{vectordb._collection.count()}")
    return vectordb
