"""Python dependency audit CI policy 的回归测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import pip_audit_policy


def build_audit_payload(
    advisory_id: str = "PYSEC-2026-311",
    *,
    aliases: list[str] | None = None,
    package: str = "chromadb",
    version: str = "1.5.9",
    fix_versions: list[str] | None = None,
) -> dict[str, object]:
    """构造最小 pip-audit JSON。"""
    return {
        "dependencies": [
            {
                "name": package,
                "version": version,
                "vulns": [
                    {
                        "id": advisory_id,
                        "aliases": aliases or ["GHSA-f4j7-r4q5-qw2c"],
                        "fix_versions": fix_versions or [],
                        "description": "test advisory",
                    }
                ],
            }
        ],
        "fixes": [],
    }


def build_exception(
    advisory_id: str = "GHSA-F4J7-R4Q5-QW2C",
    *,
    package: str = "chromadb",
    affected_version: str = "1.5.9",
    expires_on: date = date(2026, 8, 20),
) -> pip_audit_policy.AuditException:
    """构造测试安全例外。"""
    return pip_audit_policy.AuditException(
        advisory_id=advisory_id,
        package=package,
        affected_version=affected_version,
        reviewed_on=date(2026, 7, 20),
        expires_on=expires_on,
        reason="test reason",
    )


class PipAuditPolicyScriptTests(unittest.TestCase):
    """验证 Python 漏洞阻断、限时例外和清理机制。"""

    def test_clean_audit_passes_without_exceptions(self) -> None:
        """零 finding 且无例外时应通过。"""
        findings = pip_audit_policy.collect_findings(
            {"dependencies": [], "fixes": []}
        )

        result = pip_audit_policy.evaluate_policy(
            findings, [], today=date(2026, 7, 20)
        )

        self.assertTrue(result.passed)

    def test_aliases_choose_ghsa_and_duplicate_feed_entries_are_deduped(self) -> None:
        """同一 GHSA 的 PYSEC/CVE 重复记录应合并。"""
        payload = build_audit_payload()
        dependency = payload["dependencies"][0]
        dependency["vulns"].append(
            {
                "id": "CVE-2026-45829",
                "aliases": ["GHSA-f4j7-r4q5-qw2c", "PYSEC-2026-311"],
                "fix_versions": [],
                "description": "duplicate",
            }
        )

        findings = pip_audit_policy.collect_findings(payload)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].advisory_id, "GHSA-F4J7-R4Q5-QW2C")

    def test_fixable_finding_blocks_even_with_exception(self) -> None:
        """已有安全升级版本的漏洞禁止通过例外放行。"""
        findings = pip_audit_policy.collect_findings(
            build_audit_payload(fix_versions=["1.6.0"])
        )

        result = pip_audit_policy.evaluate_policy(
            findings, [build_exception()], today=date(2026, 7, 20)
        )

        self.assertFalse(result.passed)
        self.assertIn("已有修复版本", result.blocked[0])

    def test_unlisted_no_fix_finding_blocks(self) -> None:
        """没有修复版本的新 finding 也必须先完成 triage。"""
        findings = pip_audit_policy.collect_findings(build_audit_payload())

        result = pip_audit_policy.evaluate_policy(
            findings, [], today=date(2026, 7, 20)
        )

        self.assertFalse(result.passed)
        self.assertIn("未登记", result.blocked[0])

    def test_valid_no_fix_exception_passes(self) -> None:
        """有效期内精确匹配的 no-fix 例外应通过。"""
        findings = pip_audit_policy.collect_findings(build_audit_payload())

        result = pip_audit_policy.evaluate_policy(
            findings, [build_exception()], today=date(2026, 7, 20)
        )

        self.assertTrue(result.passed)
        self.assertEqual(len(result.allowed), 1)

    def test_expired_exception_blocks(self) -> None:
        """例外到期后必须阻断 CI。"""
        findings = pip_audit_policy.collect_findings(build_audit_payload())

        result = pip_audit_policy.evaluate_policy(
            findings,
            [build_exception(expires_on=date(2026, 7, 19))],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("已过期", result.blocked[0])

    def test_version_mismatch_blocks_as_stale_exception(self) -> None:
        """升级 package 后旧版本例外不能继续匹配。"""
        findings = pip_audit_policy.collect_findings(build_audit_payload())

        result = pip_audit_policy.evaluate_policy(
            findings,
            [build_exception(affected_version="1.5.8")],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertTrue(any("已无精确对应漏洞" in item for item in result.blocked))

    def test_stale_exception_blocks_until_removed(self) -> None:
        """上游修复后遗留例外应阻断并要求清理。"""
        result = pip_audit_policy.evaluate_policy(
            [], [build_exception()], today=date(2026, 7, 20)
        )

        self.assertFalse(result.passed)
        self.assertIn("已无精确对应漏洞", result.blocked[0])

    def test_load_exceptions_rejects_more_than_31_days(self) -> None:
        """例外不能通过超长有效期退化为永久白名单。"""
        payload = {
            "version": 1,
            "exceptions": [
                {
                    "advisory_id": "GHSA-F4J7-R4Q5-QW2C",
                    "package": "chromadb",
                    "affected_version": "1.5.9",
                    "reviewed_on": "2026-07-20",
                    "expires_on": "2026-08-21",
                    "reason": "too long",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "exceptions.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "不能超过 31 天"):
                pip_audit_policy.load_exceptions(path)

    @patch("scripts.pip_audit_policy.subprocess.run")
    def test_scanner_failure_does_not_pass(self, run_mock: unittest.mock.Mock) -> None:
        """resolver 或网络错误不能被误判为零 finding。"""
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="{}", stderr="resolver failed"
        )

        with self.assertRaisesRegex(ValueError, "执行失败"):
            pip_audit_policy.run_pip_audit(Path("requirements.txt"))


if __name__ == "__main__":
    unittest.main()
