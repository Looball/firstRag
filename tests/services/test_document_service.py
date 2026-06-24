"""文档发现与切分服务的单元测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.services.documents.document_service import get_document_paths


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


if __name__ == "__main__":
    unittest.main()
