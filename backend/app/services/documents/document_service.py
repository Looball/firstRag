import logging
import os
from pathlib import Path
from uuid import UUID

from langchain_chroma import Chroma

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

from app.core.config import VECTOR_STORE_PATH
from app.services.vectors.embedding_model import create_embedding_model


logger = logging.getLogger(__name__)

SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
SUPPORTED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
    "application/markdown",
    "text/x-markdown",
    "text/markdown",
    "text/plain",
}
MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
    ("#####", "h5"),
    ("######", "h6"),
]
TEXT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


class UnsupportedDocumentTypeError(ValueError):
    """文件类型不在知识库解析支持范围内时抛出。"""


class EmptyDocumentError(ValueError):
    """文件可读取但没有解析出可入库文本时抛出。"""


def get_supported_document_type_text() -> str:
    """返回面向用户展示的支持文件类型说明。"""
    return "PDF、DOCX、Markdown 或 TXT"


def is_supported_document_file(
    file_name: str,
    mime_type: str | None = None,
) -> bool:
    """判断上传文件是否属于当前解析链路支持的类型。"""
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return False

    if not mime_type:
        return True

    normalized_mime_type = mime_type.split(";", maxsplit=1)[0].strip().lower()
    return (
        not normalized_mime_type
        or normalized_mime_type in SUPPORTED_DOCUMENT_MIME_TYPES
    )


def build_unsupported_document_type_message(file_name: str) -> str:
    """生成不支持文件类型的安全错误信息。"""
    suffix = Path(file_name).suffix.lower() or "无扩展名"
    return (
        f"不支持的文件类型：{suffix}。"
        f"请上传 {get_supported_document_type_text()} 文件。"
    )


def get_document_paths(folder_path: str | Path = "./local_doc") -> list[Path]:
    """获取本地知识库中的PDF和Markdown文件路径。"""
    document_paths = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS:
                document_paths.append(file_path)

    # 文件系统遍历顺序不保证稳定；固定排序可避免批量建库时文件 ID 随运行变化。
    return sorted(document_paths)


def convert_docx2md(docx_path) -> str:
    """将 DOCX 转换为 Markdown，并忽略内嵌图片。"""

    with open(docx_path, "rb") as file:
        result = mammoth.convert_to_html(
            file,
            convert_image=lambda image: [],
        )

    return markdownify(result.value, heading_style="ATX")


def load_document(
    file_path: Path,
    file_id: UUID | str,
    user_id: int | str | None = None,
) -> list[Document]:
    """根据文件类型加载单个本地文档。"""
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise UnsupportedDocumentTypeError(
            build_unsupported_document_type_message(file_path.name),
        )

    base_metadata = {
        "source": str(file_path),
        "file_name": file_path.name,
        "file_id": str(file_id),
        "file_type": suffix.removeprefix("."),
    }
    if user_id is not None:
        base_metadata["user_id"] = str(user_id)

    if suffix == ".pdf":
        markdown_text = pymupdf4llm.to_markdown(str(file_path))
        return [
            Document(
                page_content=markdown_text,
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                },
            )
        ]

    if suffix == ".docx":
        markdown_text = convert_docx2md(str(file_path))
        return [
            Document(
                page_content=markdown_text,
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                },
            )
        ]

    if suffix == ".md":
        return [
            Document(
                page_content=file_path.read_text(encoding="utf-8"),
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                },
            )
        ]

    if suffix == ".txt":
        return [
            Document(
                page_content=file_path.read_text(encoding="utf-8"),
                metadata={
                    **base_metadata,
                    "content_format": "plain_text",
                },
            )
        ]

    raise UnsupportedDocumentTypeError(
        build_unsupported_document_type_message(file_path.name),
    )


def split_document(document: Document) -> list[Document]:
    """按照文档内容格式切分单个文档。"""
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    markdown_chunk_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=TEXT_SEPARATORS,
    )
    plain_text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=TEXT_SEPARATORS,
    )

    if document.metadata.get("content_format") == "markdown":
        sections = markdown_splitter.split_text(document.page_content)
        for section in sections:
            # 标题切分器生成标题元数据，这里补回原始文件信息。
            section.metadata = {
                **document.metadata,
                **section.metadata,
            }
        return markdown_chunk_splitter.split_documents(sections)

    return plain_text_splitter.split_documents([document])


def split_documents(documents: list[Document]) -> list[Document]:
    """批量切分文档，并为每个源文档生成独立的分块序号。"""
    chunks: list[Document] = []
    for document in documents:
        document_chunks = split_document(document)
        for chunk_index, chunk in enumerate(document_chunks):
            chunk.metadata["chunk_index"] = chunk_index
        chunks.extend(document_chunks)

    return chunks


def build_vector_store(
    folder_path: str | Path = "./local_doc",
    persist_directory: str | Path = VECTOR_STORE_PATH,
) -> Chroma:
    """加载、切分本地文档并写入Chroma向量数据库。"""
    file_paths = get_document_paths(folder_path)
    logger.info("发现可入库文档数量：%s", len(file_paths))
    logger.debug("文档发现样例：%s", [str(path) for path in file_paths[:3]])

    documents = []
    for index, file_path in enumerate(file_paths):
        documents.extend(load_document(file_path, file_id=str(index)))

    split_docs = split_documents(documents)
    character_count = sum(len(doc.page_content) for doc in split_docs)

    logger.info(
        "文档切分完成：chunks=%s characters=%s",
        len(split_docs),
        character_count,
    )
    logger.debug("文档切分样例：%s", split_docs[:3])

    vectordb = Chroma.from_documents(
        documents=split_docs,
        embedding=create_embedding_model(),
        persist_directory=str(persist_directory),
    )
    logger.info("向量库中存储的数量：%s", vectordb._collection.count())
    return vectordb


if __name__ == '__main__':
    docs = load_document(
        Path('../../../demo/local_doc/预训练模型微调.pdf'),
        file_id='123125',
    )
    print(docs)
    chunks = split_documents(docs)
    print(chunks)
    for chunk in chunks:
        print('*'*40)
        print(chunk.page_content)
