"""文档发现与切分服务的单元测试。"""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from app.services.documents.document_service import (
    build_vector_store,
    get_document_paths,
)


class DocumentServiceTests(unittest.TestCase):
    """验证文档扫描结果的过滤和稳定性。"""

    def test_get_document_paths_returns_sorted_supported_files(self) -> None:
        """支持的文件应按路径排序，且忽略不支持的扩展名。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested_directory = root / "nested"
            nested_directory.mkdir()
            for relative_path in (
                "z-last.txt",
                "a-first.md",
                "nested/middle.PDF",
                "ignored.png",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            document_paths = get_document_paths(root)

        self.assertEqual(
            document_paths,
            sorted(
                [
                    root / "a-first.md",
                    root / "nested" / "middle.PDF",
                    root / "z-last.txt",
                ]
            ),
        )

    def test_build_vector_store_does_not_print_debug_output(self) -> None:
        """批量建库应使用 logger 记录进度，避免默认污染 stdout。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "sample.md").write_text("# 标题\n\n正文内容", encoding="utf-8")
            persist_directory = root / "vector_db"

            mock_vector_store = Mock()
            mock_vector_store._collection.count.return_value = 1
            stdout = StringIO()

            with patch(
                "app.services.documents.document_service.create_embedding_model",
                return_value=Mock(),
            ) as mock_create_embedding_model, patch(
                "app.services.documents.document_service.Chroma.from_documents",
                return_value=mock_vector_store,
            ), redirect_stdout(stdout):
                result = build_vector_store(
                    folder_path=root,
                    persist_directory=persist_directory,
                    user_id=42,
                )

        self.assertIs(result, mock_vector_store)
        self.assertEqual(stdout.getvalue(), "")
        mock_create_embedding_model.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
