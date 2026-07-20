"""GitHub Actions 完整 SHA pin policy 的回归测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import check_github_actions_pins


class GitHubActionsPinsScriptTests(unittest.TestCase):
    """验证完整 SHA、版本注释和本地 Action 处理。"""

    def _collect(self, workflow: str) -> list[check_github_actions_pins.ActionReference]:
        """写入临时 workflow 并收集 Action 引用。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ci.yml"
            path.write_text(workflow, encoding="utf-8")
            return check_github_actions_pins.collect_action_references([path])

    def test_full_sha_with_release_comment_passes(self) -> None:
        """完整 SHA 和同一行 release tag 注释应通过。"""
        references = self._collect(
            "steps:\n"
            "  - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2\n"
        )

        violations = check_github_actions_pins.validate_action_references(references)

        self.assertEqual(violations, [])

    def test_version_tag_is_blocked(self) -> None:
        """可移动 version tag 必须被阻断。"""
        references = self._collect(
            "steps:\n  - uses: actions/checkout@v6 # v6.0.2\n"
        )

        violations = check_github_actions_pins.validate_action_references(references)

        self.assertIn("40 位 commit SHA", violations[0])

    def test_short_sha_is_blocked(self) -> None:
        """缩写 SHA 仍可产生歧义，必须被阻断。"""
        references = self._collect(
            "steps:\n  - uses: actions/checkout@de0fac2 # v6.0.2\n"
        )

        violations = check_github_actions_pins.validate_action_references(references)

        self.assertIn("40 位 commit SHA", violations[0])

    def test_missing_release_comment_is_blocked(self) -> None:
        """缺失 release tag 注释会降低 Dependabot 更新可读性。"""
        references = self._collect(
            "steps:\n"
            "  - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd\n"
        )

        violations = check_github_actions_pins.validate_action_references(references)

        self.assertIn("release tag 注释", violations[0])

    def test_local_and_docker_actions_are_outside_policy(self) -> None:
        """本地 Action 和 docker:// 引用不使用 GitHub repository SHA 规则。"""
        references = self._collect(
            "steps:\n"
            "  - uses: ./.github/actions/local\n"
            "  - uses: docker://alpine:3.22\n"
        )

        self.assertEqual(references, [])

    def test_quoted_action_reference_is_supported(self) -> None:
        """YAML 引号不应影响 Action pin 解析。"""
        references = self._collect(
            "steps:\n"
            "  - uses: 'actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238' # v6.2.0\n"
        )

        violations = check_github_actions_pins.validate_action_references(references)

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
