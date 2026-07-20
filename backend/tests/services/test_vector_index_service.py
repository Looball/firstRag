"""向量索引服务回归测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.vectors.vector_index_service import (
    get_vector_store,
    index_file_vectors,
)


class VectorIndexServiceTests(unittest.TestCase):
    """验证文件记录字段能够正确传入文档解析层。"""

    def test_index_file_vectors_forwards_original_file_name(self) -> None:
        """索引时应使用用户上传文件名，而不是引用未定义的文件记录。"""
        file_id = uuid4()
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "stored-file"
            storage_path.write_text("测试内容", encoding="utf-8")

            with patch(
                "app.services.vectors.vector_index_service.load_document",
                side_effect=RuntimeError("stop-after-loader"),
            ) as load_document:
                with self.assertRaisesRegex(RuntimeError, "stop-after-loader"):
                    index_file_vectors(
                        user_id=1,
                        file_id=file_id,
                        storage_path=storage_path,
                        index_version=0,
                        original_name="用户上传文件.txt",
                    )

        load_document.assert_called_once_with(
            file_path=storage_path,
            file_id=file_id,
            user_id=1,
            original_name="用户上传文件.txt",
        )

    def test_get_vector_store_uses_http_client_when_host_is_configured(
        self,
    ) -> None:
        """Compose 配置 Chroma host 后应连接独立 server。"""
        with patch(
            "app.services.vectors.vector_index_service.CHROMA_HOST",
            "chroma",
        ), patch(
            "app.services.vectors.vector_index_service.CHROMA_PORT",
            8000,
        ), patch(
            "app.services.vectors.vector_index_service.CHROMA_SSL",
            False,
        ), patch(
            "app.services.vectors.vector_index_service.Chroma",
        ) as chroma:
            get_vector_store(collection_name="test-collection")

        chroma.assert_called_once_with(
            collection_name="test-collection",
            embedding_function=None,
            host="chroma",
            port=8000,
            ssl=False,
        )

    def test_get_vector_store_keeps_embedded_mode_without_host(self) -> None:
        """未配置 Chroma host 时应保留单进程本地持久化模式。"""
        with patch(
            "app.services.vectors.vector_index_service.CHROMA_HOST",
            "",
        ), patch(
            "app.services.vectors.vector_index_service.Chroma",
        ) as chroma:
            get_vector_store(
                persist_directory="/tmp/firstrag-test-chroma",
                collection_name="test-collection",
            )

        chroma.assert_called_once_with(
            collection_name="test-collection",
            embedding_function=None,
            persist_directory="/tmp/firstrag-test-chroma",
        )


if __name__ == "__main__":
    unittest.main()
