import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
# 将docx转为md文件
import mammoth
from markdownify import markdownify
# 将PDF转为md文件
import pymupdf4llm

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.services.vectors.embedding_model import ZhipuAIEmbeddings

def get_document_paths(folder_path: str | Path = "./local_doc") -> list[Path]:
    """获取本地知识库中的PDF和Markdown文件路径。"""
    supported_extensions = {".pdf", ".md", ".txt", ".docx"}
    document_paths = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() in supported_extensions:
                document_paths.append(file_path)

    return document_paths

def convert_docx2md(docx_path) -> str:
    """将 DOCX 转换为 Markdown，并忽略内嵌图片。"""

    with open(docx_path, "rb") as file:
        result = mammoth.convert_to_html(
            file,
            convert_image=lambda image: [],
        )

    return markdownify(result.value, heading_style="ATX")

def load_documents(file_paths: list[Path]) -> list[Document]:
    """根据文件类型加载本地文档。"""
    documents = []

    for file_path in file_paths:
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            markdown_text = pymupdf4llm.to_markdown(str(file_path))
            # 将字符串对象转换为document对象
            documents.append(
                Document(
                    page_content=markdown_text,
                    metadata={
                        "source": str(file_path),
                        "file_name": file_path.name,
                        "file_type": suffix.removeprefix("."),
                        "content_format": "markdown",
                    },
                )
            )
            continue
        elif suffix == ".docx":
            markdown_text = convert_docx2md(str(file_path))
            # 将字符串对象转换为document对象
            documents.append(
                Document(
                    page_content=markdown_text,
                    metadata={
                        "source": str(file_path),
                        "file_name": file_path.name,
                        "file_type": suffix.removeprefix("."),
                        "content_format": "markdown",
                    },
                )
            )
            continue
        elif suffix == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif suffix == ".md":
            documents.append(
                Document(
                    page_content=file_path.read_text(encoding="utf-8"),
                    metadata={
                        "source": str(file_path),
                        "file_name": file_path.name,
                        "file_type": suffix.removeprefix("."),
                        "content_format": "markdown",
                    },
                )
            )
            continue
        else:
            continue

        loaded_documents = loader.load()
        for document in loaded_documents:
            document.metadata.update(
                {
                    "file_name": file_path.name,
                    "file_type": suffix.removeprefix("."),
                    "content_format": "plain_text",
                }
            )
        documents.extend(loaded_documents)

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """按照 Markdown 标题或纯文本段落结构切分文档。"""
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
            ("####", "h4"),
            ("#####", "h5"),
            ("######", "h6"),
        ],
        strip_headers=False,
    )
    markdown_chunk_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )
    plain_text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    chunks: list[Document] = []
    for document in documents:
        if document.metadata.get("content_format") == "markdown":
            sections = markdown_splitter.split_text(document.page_content)
            for section in sections:
                # 标题切分器生成标题元数据，这里补回原始文件信息。
                section.metadata = {
                    **document.metadata,
                    **section.metadata,
                }
            document_chunks = markdown_chunk_splitter.split_documents(sections)
        else:
            document_chunks = plain_text_splitter.split_documents([document])

        for chunk_index, chunk in enumerate(document_chunks):
            chunk.metadata["chunk_index"] = chunk_index
        chunks.extend(document_chunks)

    return chunks


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


if __name__ == '__main__':
    ...
