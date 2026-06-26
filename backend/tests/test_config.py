"""配置路径解析的回归测试。"""

import unittest
from pathlib import Path

from app.core.config import PROJECT_ROOT, resolve_project_path


class ConfigPathTests(unittest.TestCase):
    """验证路径型配置不受后端启动目录影响。"""

    def test_relative_path_resolves_from_project_root(self) -> None:
        """相对路径应固定解析到项目根目录。"""
        self.assertEqual(
            resolve_project_path("vector_db/chroma", PROJECT_ROOT / "fallback"),
            PROJECT_ROOT / "vector_db/chroma",
        )

    def test_absolute_path_is_kept(self) -> None:
        """绝对路径应按用户显式配置保留。"""
        absolute_path = Path("/tmp/firstrag-vector-db")

        self.assertEqual(
            resolve_project_path(absolute_path, PROJECT_ROOT / "fallback"),
            absolute_path,
        )


if __name__ == "__main__":
    unittest.main()
