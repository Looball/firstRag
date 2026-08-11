"""教程文档回归检查脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import check_tutorial_docs  # noqa: E402
from scripts import generate_tutorial_ocr_fixture  # noqa: E402


class TutorialDocsScriptTests(unittest.TestCase):
    """验证链接、章节、敏感信息和命令检查会给出可定位结果。"""

    def _build_repository(self, root: Path) -> Path:
        """创建满足最小 manifest 的临时教程仓库。"""
        tutorial_root = root / "docs/tutorials"
        fixture_root = tutorial_root / "fixtures"
        workflow_root = root / ".github/workflows"
        script_root = root / "scripts"
        source_root = root / "backend/app"
        fixture_root.mkdir(parents=True)
        workflow_root.mkdir(parents=True)
        script_root.mkdir(parents=True)
        source_root.mkdir(parents=True)
        chapter_path = tutorial_root / "CHAPTER.md"
        chapter_path.write_text(
            "# Chapter\n\n"
            "[source](../../backend/app/example.py)\n\n"
            "## 基础练习\n\n"
            "## 诊断练习\n\n"
            "## 扩展练习\n",
            encoding="utf-8",
        )
        (tutorial_root / "README.md").write_text(
            "# Index\n\n[Chapter](CHAPTER.md)\n",
            encoding="utf-8",
        )
        (fixture_root / "sample.txt").write_text(
            "synthetic tutorial fixture\n",
            encoding="utf-8",
        )
        (source_root / "example.py").write_text(
            '"""example"""\n',
            encoding="utf-8",
        )
        (workflow_root / "ci.yml").write_text(
            "steps:\n  - run: python3 scripts/check_tutorial_docs.py\n",
            encoding="utf-8",
        )
        (script_root / "check_tutorial_docs.py").write_text(
            '"""placeholder"""\n',
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "index_path": "docs/tutorials/README.md",
            "ci_workflow_path": ".github/workflows/ci.yml",
            "forbidden_current_runtime_patterns": ["当前 Chroma runtime"],
            "core_chapters": [
                {
                    "path": "docs/tutorials/CHAPTER.md",
                    "title": "Chapter",
                    "required_headings": [
                        "基础练习",
                        "诊断练习",
                        "扩展练习",
                    ],
                    "credential_free_heading": "基础练习",
                }
            ],
            "fixtures": [
                {
                    "path": "docs/tutorials/fixtures/sample.txt",
                    "kind": "retrieval",
                    "origin": "repository-authored-synthetic",
                }
            ],
        }
        manifest_path = tutorial_root / "tutorial_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return chapter_path

    def test_current_repository_passes(self) -> None:
        """当前 checkout 的教程文档应满足全部门禁。"""
        violations = check_tutorial_docs.collect_violations(REPOSITORY_ROOT)
        self.assertEqual(violations, [])

    def test_missing_source_link_reports_file_and_target(self) -> None:
        """删除被教程链接的源码文件时应明确指出失效目标。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_repository(root)
            (root / "backend/app/example.py").unlink()

            violations = check_tutorial_docs.collect_violations(root)

        messages = [item.format(root) for item in violations]
        self.assertTrue(
            any(
                "docs/tutorials/CHAPTER.md:3" in message
                and "链接目标不存在" in message
                and "example.py" in message
                for message in messages
            )
        )

    def test_missing_exercise_heading_reports_chapter(self) -> None:
        """核心章节缺少 manifest heading 时应定位到章节。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            chapter_path = self._build_repository(root)
            chapter_path.write_text(
                chapter_path.read_text(encoding="utf-8").replace(
                    "## 诊断练习\n",
                    "",
                ),
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any(
                item.path.name == "CHAPTER.md"
                and "缺少 manifest 声明的 heading：诊断练习" in item.message
                for item in violations
            )
        )

    def test_missing_index_link_reports_core_chapter(self) -> None:
        """教程索引遗漏核心章节时应显示 manifest 路径。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_repository(root)
            (root / "docs/tutorials/README.md").write_text(
                "# Index\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any(
                "教程索引未链接核心章节：docs/tutorials/CHAPTER.md"
                in item.message
                for item in violations
            )
        )

    def test_missing_ci_command_reports_workflow(self) -> None:
        """required workflow 移除教程检查时应阻断。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_repository(root)
            (root / ".github/workflows/ci.yml").write_text(
                "steps:\n  - run: python3 -V\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any(
                "CI 未执行 `python3 scripts/check_tutorial_docs.py`"
                in item.message
                for item in violations
            )
        )

    def test_broken_anchor_reports_exact_link(self) -> None:
        """不存在的章节 anchor 应显示原始链接。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            chapter_path = self._build_repository(root)
            chapter_path.write_text(
                chapter_path.read_text(encoding="utf-8")
                + "\n[missing](#不存在的章节)\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any(
                "章节 anchor 不存在：#不存在的章节" in item.message
                for item in violations
            )
        )

    def test_sensitive_key_pattern_is_blocked(self) -> None:
        """高置信度的可用 Key 形态不能进入教程素材。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            chapter_path = self._build_repository(root)
            chapter_path.write_text(
                chapter_path.read_text(encoding="utf-8")
                + "\nsk-abcdefghijklmnopqrstuvwxyz123456\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any(
                "疑似可用敏感信息（OpenAI-style key）" in item.message
                for item in violations
            )
        )

    def test_legacy_compose_command_is_blocked(self) -> None:
        """教程 shell block 不允许恢复到 Compose v1 命令。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            chapter_path = self._build_repository(root)
            chapter_path.write_text(
                chapter_path.read_text(encoding="utf-8")
                + "\n```bash\ndocker-compose ps\n```\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any("Docker Compose v2" in item.message for item in violations)
        )

    def test_ocr_fixture_generator_uses_explicit_ground_truth(self) -> None:
        """OCR 生成器应从受控文本创建可读取的 PNG。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / "ground-truth.txt"
            output_path = root / "card.png"
            source_path.write_text("SYNTHETIC OCR\nMARKER 417\n", encoding="utf-8")

            exit_code = generate_tutorial_ocr_fixture.main(
                ["--source", str(source_path), "--output", str(output_path)]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_current_chroma_runtime_fragment_is_blocked(self) -> None:
        """教程不得恢复已冻结的 Chroma 当前运行时说法。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            chapter_path = self._build_repository(root)
            chapter_path.write_text(
                chapter_path.read_text(encoding="utf-8")
                + "\n当前 Chroma runtime\n",
                encoding="utf-8",
            )

            violations = check_tutorial_docs.collect_violations(root)

        self.assertTrue(
            any("当前 Milvus 基线" in item.message for item in violations)
        )


if __name__ == "__main__":
    unittest.main()
