"""npm dependency audit CI policy 的回归测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import npm_audit_policy


def build_audit_payload(
    advisory_id: str,
    *,
    package: str = "postcss",
    severity: str = "moderate",
) -> dict[str, object]:
    """构造最小 npm audit JSON。"""
    return {
        "auditReportVersion": 2,
        "vulnerabilities": {
            package: {
                "name": package,
                "severity": severity,
                "via": [
                    {
                        "source": 123,
                        "name": package,
                        "title": "test advisory",
                        "url": (
                            "https://github.com/advisories/"
                            f"{advisory_id}"
                        ),
                        "severity": severity,
                    }
                ],
            }
        },
    }


def build_exception(
    advisory_id: str = "GHSA-QX2V-QP2M-JG93",
    *,
    package: str = "postcss",
    severity: str = "moderate",
    expires_on: date = date(2026, 8, 20),
) -> npm_audit_policy.AuditException:
    """构造测试安全例外。"""
    return npm_audit_policy.AuditException(
        advisory_id=advisory_id,
        package=package,
        severity=severity,
        reviewed_on=date(2026, 7, 20),
        expires_on=expires_on,
        reason="test reason",
    )


class NpmAuditPolicyScriptTests(unittest.TestCase):
    """验证漏洞阻断、限时例外和清理机制。"""

    def test_valid_moderate_exception_passes(self) -> None:
        """有效期内精确匹配的 moderate 例外应通过。"""
        findings = npm_audit_policy.collect_findings(
            build_audit_payload("GHSA-qx2v-qp2m-jg93")
        )

        result = npm_audit_policy.evaluate_policy(
            findings,
            [build_exception()],
            today=date(2026, 7, 20),
        )

        self.assertTrue(result.passed)
        self.assertEqual(len(result.allowed), 1)

    def test_expired_exception_blocks(self) -> None:
        """例外到期后必须阻断 CI。"""
        findings = npm_audit_policy.collect_findings(
            build_audit_payload("GHSA-qx2v-qp2m-jg93")
        )

        result = npm_audit_policy.evaluate_policy(
            findings,
            [build_exception(expires_on=date(2026, 7, 19))],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("已过期", result.blocked[0])

    def test_high_finding_cannot_be_exempted(self) -> None:
        """high/critical finding 即使有同名例外也必须阻断。"""
        findings = npm_audit_policy.collect_findings(
            build_audit_payload(
                "GHSA-AAAA-BBBB-CCCC",
                package="next",
                severity="high",
            )
        )
        exception = build_exception(
            "GHSA-AAAA-BBBB-CCCC",
            package="next",
            severity="high",
        )

        result = npm_audit_policy.evaluate_policy(
            findings,
            [exception],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("禁止例外", result.blocked[0])

    def test_unlisted_moderate_finding_blocks(self) -> None:
        """新的 moderate finding 必须先经过 triage 才能进入 CI。"""
        findings = npm_audit_policy.collect_findings(
            build_audit_payload("GHSA-AAAA-BBBB-CCCC")
        )

        result = npm_audit_policy.evaluate_policy(
            findings,
            [],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("未登记", result.blocked[0])

    def test_high_string_only_dependency_chain_blocks(self) -> None:
        """缺少 advisory 对象的 high 传播节点也不能漏检。"""
        payload = {
            "auditReportVersion": 2,
            "vulnerabilities": {
                "framework": {
                    "name": "framework",
                    "severity": "high",
                    "via": ["transitive-package"],
                }
            },
        }

        findings = npm_audit_policy.collect_findings(payload)
        result = npm_audit_policy.evaluate_policy(
            findings,
            [],
            today=date(2026, 7, 20),
        )

        self.assertEqual(findings[0].advisory_id, "NPM-PACKAGE-FRAMEWORK")
        self.assertFalse(result.passed)
        self.assertIn("禁止例外", result.blocked[0])

    def test_stale_exception_blocks_until_removed(self) -> None:
        """上游修复后遗留例外应阻断并要求清理。"""
        result = npm_audit_policy.evaluate_policy(
            [],
            [build_exception()],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("已无对应漏洞", result.blocked[0])

    def test_severity_downgrade_requires_exception_cleanup(self) -> None:
        """finding 降为 low 后也应删除原 moderate 例外。"""
        findings = npm_audit_policy.collect_findings(
            build_audit_payload(
                "GHSA-qx2v-qp2m-jg93",
                severity="low",
            )
        )

        result = npm_audit_policy.evaluate_policy(
            findings,
            [build_exception()],
            today=date(2026, 7, 20),
        )

        self.assertFalse(result.passed)
        self.assertIn("severity 不匹配", result.blocked[0])

    def test_load_exceptions_rejects_high_severity(self) -> None:
        """例外文件本身不得登记 high/critical。"""
        payload = {
            "version": 1,
            "exceptions": [
                {
                    "advisory_id": "GHSA-AAAA-BBBB-CCCC",
                    "package": "next",
                    "severity": "high",
                    "reviewed_on": "2026-07-20",
                    "expires_on": "2026-08-20",
                    "reason": "not allowed",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "exceptions.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "禁止加入例外"):
                npm_audit_policy.load_exceptions(path)

    def test_load_exceptions_rejects_more_than_31_days(self) -> None:
        """例外不能通过超长有效期退化为永久白名单。"""
        payload = {
            "version": 1,
            "exceptions": [
                {
                    "advisory_id": "GHSA-QX2V-QP2M-JG93",
                    "package": "postcss",
                    "severity": "moderate",
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
                npm_audit_policy.load_exceptions(path)


if __name__ == "__main__":
    unittest.main()
