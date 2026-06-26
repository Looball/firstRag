"""兼容入口：文档处理服务实现位于app.services。"""

from app.services.documents.document_service import (
    build_vector_store,
    get_document_paths,
    load_document,
    split_documents,
)
from app.services.vectors.embedding_model import ZhipuAIEmbeddings

__all__ = [
    "ZhipuAIEmbeddings",
    "build_vector_store",
    "get_document_paths",
    "load_document",
    "split_documents",
]


def main() -> None:
    build_vector_store()


if __name__ == "__main__":
    main()
