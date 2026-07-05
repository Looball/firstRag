"""配置路径解析的回归测试。"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import PROJECT_ROOT, read_float_env, resolve_project_path


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

    def test_read_float_env_falls_back_for_invalid_value(self) -> None:
        """浮点型配置非法时应回退到默认值。"""
        with patch.dict(os.environ, {"REDIS_COMMAND_TIMEOUT_SECONDS": "oops"}):
            self.assertEqual(
                read_float_env("REDIS_COMMAND_TIMEOUT_SECONDS", 1.5),
                1.5,
            )

    def test_read_float_env_reads_valid_value(self) -> None:
        """浮点型配置合法时应按环境变量读取。"""
        with patch.dict(os.environ, {"REDIS_COMMAND_TIMEOUT_SECONDS": "2.25"}):
            self.assertEqual(
                read_float_env("REDIS_COMMAND_TIMEOUT_SECONDS", 1.5),
                2.25,
            )


if __name__ == "__main__":
    unittest.main()
