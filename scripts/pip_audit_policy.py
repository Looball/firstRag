"""执行 Python dependency 审计并校验限时安全例外。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


MAX_EXCEPTION_DAYS = 31


def normalize_package_name(value: str) -> str:
    """按 Python package name 规范统一比较格式。"""
    return re.sub(r"[-_.]+", "-", value.strip()).lower()


@dataclass(frozen=True)
class AuditFinding:
    """表示 pip-audit 返回的一条去重漏洞。"""

    advisory_id: str
    identifiers: tuple[str, ...]
    package: str
    version: str
    fix_versions: tuple[str, ...]
    description: str

    @property
    def has_fix(self) -> bool:
        """上游提供至少一个修复版本时返回 True。"""
        return bool(self.fix_versions)


@dataclass(frozen=True)
class AuditException:
    """表示完成 triage、精确到版本且带到期日的例外。"""

    advisory_id: str
    package: str
    affected_version: str
    reviewed_on: date
    expires_on: date
    reason: str


@dataclass(frozen=True)
class PolicyResult:
    """保存 Python dependency 审计策略判断结果。"""

    blocked: tuple[str, ...]
    allowed: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """没有阻断项时返回 True。"""
        return not self.blocked


def _parse_iso_date(value: Any, field_name: str) -> date:
    """解析 YYYY-MM-DD 日期并生成可读错误。"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是 YYYY-MM-DD 字符串。")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是有效的 YYYY-MM-DD 日期。") from exc


def _canonical_advisory_id(identifiers: set[str]) -> str:
    """优先选择稳定的 GHSA，再回退到扫描器主 ID。"""
    for prefix in ("GHSA-", "PYSEC-", "CVE-"):
        matches = sorted(item for item in identifiers if item.startswith(prefix))
        if matches:
            return matches[0]
    return sorted(identifiers)[0]


def collect_findings(payload: dict[str, Any]) -> list[AuditFinding]:
    """从 pip-audit JSON 中提取、规范化并去重漏洞。"""
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("pip-audit JSON 缺少 dependencies 数组。")

    findings: dict[tuple[str, str, str], AuditFinding] = {}
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        package = normalize_package_name(str(dependency.get("name") or ""))
        version = str(dependency.get("version") or "").strip()
        vulnerabilities = dependency.get("vulns") or []
        if not package or not version or not isinstance(vulnerabilities, list):
            continue
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            primary_id = str(vulnerability.get("id") or "").strip().upper()
            aliases = vulnerability.get("aliases") or []
            if not isinstance(aliases, list):
                raise ValueError(
                    f"{package} {version} 的 vulnerability aliases 必须是数组。"
                )
            identifiers = {
                str(item).strip().upper()
                for item in [primary_id, *aliases]
                if str(item).strip()
            }
            if not identifiers:
                raise ValueError(f"{package} {version} 的 vulnerability 缺少 ID。")
            advisory_id = _canonical_advisory_id(identifiers)
            raw_fix_versions = vulnerability.get("fix_versions") or []
            if not isinstance(raw_fix_versions, list):
                raise ValueError(
                    f"{advisory_id} 的 fix_versions 必须是数组。"
                )
            fix_versions = tuple(
                sorted({str(item).strip() for item in raw_fix_versions if str(item).strip()})
            )
            finding = AuditFinding(
                advisory_id=advisory_id,
                identifiers=tuple(sorted(identifiers)),
                package=package,
                version=version,
                fix_versions=fix_versions,
                description=str(vulnerability.get("description") or "").strip(),
            )
            key = (finding.advisory_id, finding.package, finding.version)
            existing = findings.get(key)
            if existing is None:
                findings[key] = finding
                continue
            findings[key] = AuditFinding(
                advisory_id=finding.advisory_id,
                identifiers=tuple(sorted(set(existing.identifiers) | identifiers)),
                package=finding.package,
                version=finding.version,
                fix_versions=tuple(
                    sorted(set(existing.fix_versions) | set(finding.fix_versions))
                ),
                description=existing.description or finding.description,
            )

    return sorted(
        findings.values(),
        key=lambda item: (item.package, item.advisory_id, item.version),
    )


def load_exceptions(path: Path) -> list[AuditException]:
    """读取并严格校验 Python dependency 安全例外清单。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"安全例外文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"安全例外文件不是有效 JSON：{path}") from exc

    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("安全例外文件 version 必须为 1。")
    raw_exceptions = payload.get("exceptions")
    if not isinstance(raw_exceptions, list):
        raise ValueError("安全例外文件 exceptions 必须是数组。")

    exceptions: list[AuditException] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_exceptions):
        if not isinstance(item, dict):
            raise ValueError(f"exceptions[{index}] 必须是对象。")
        advisory_id = str(item.get("advisory_id") or "").strip().upper()
        package = normalize_package_name(str(item.get("package") or ""))
        affected_version = str(item.get("affected_version") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not advisory_id or not package or not affected_version or not reason:
            raise ValueError(
                f"exceptions[{index}] 必须包含 advisory_id、package、"
                "affected_version 和 reason。"
            )
        reviewed_on = _parse_iso_date(item.get("reviewed_on"), "reviewed_on")
        expires_on = _parse_iso_date(item.get("expires_on"), "expires_on")
        if expires_on < reviewed_on:
            raise ValueError("expires_on 不能早于 reviewed_on。")
        if (expires_on - reviewed_on).days > MAX_EXCEPTION_DAYS:
            raise ValueError(f"安全例外有效期不能超过 {MAX_EXCEPTION_DAYS} 天。")
        key = (advisory_id, package, affected_version)
        if key in seen:
            raise ValueError(
                f"安全例外重复：{advisory_id} / {package} / {affected_version}。"
            )
        seen.add(key)
        exceptions.append(
            AuditException(
                advisory_id=advisory_id,
                package=package,
                affected_version=affected_version,
                reviewed_on=reviewed_on,
                expires_on=expires_on,
                reason=reason,
            )
        )
    return exceptions


def evaluate_policy(
    findings: list[AuditFinding],
    exceptions: list[AuditException],
    *,
    today: date,
) -> PolicyResult:
    """阻断可修复漏洞，并仅允许 no-fix finding 使用限时例外。"""
    blocked: list[str] = []
    allowed: list[str] = []
    warnings: list[str] = []
    matched_exceptions: set[AuditException] = set()

    for finding in findings:
        label = f"{finding.advisory_id} package={finding.package} version={finding.version}"
        exception = next(
            (
                item
                for item in exceptions
                if item.advisory_id in finding.identifiers
                and item.package == finding.package
                and item.affected_version == finding.version
            ),
            None,
        )
        if exception is not None:
            matched_exceptions.add(exception)

        if finding.has_fix:
            blocked.append(
                f"已有修复版本，禁止例外：{label} "
                f"fix_versions={','.join(finding.fix_versions)}"
            )
            continue
        if exception is None:
            blocked.append(f"未登记的 no-fix 漏洞：{label}")
            continue
        if today < exception.reviewed_on:
            blocked.append(
                f"安全例外尚未到 reviewed_on：{label} "
                f"reviewed_on={exception.reviewed_on}"
            )
            continue
        if today > exception.expires_on:
            blocked.append(
                f"安全例外已过期：{label} expires_on={exception.expires_on}"
            )
            continue
        allowed.append(f"限时 no-fix 例外：{label} expires_on={exception.expires_on}")
        if (exception.expires_on - today).days <= 7:
            warnings.append(
                f"安全例外将在 7 天内到期：{finding.advisory_id} "
                f"expires_on={exception.expires_on}"
            )

    for exception in exceptions:
        if exception not in matched_exceptions:
            blocked.append(
                "安全例外已无精确对应漏洞，请删除："
                f"{exception.advisory_id} package={exception.package} "
                f"version={exception.affected_version}"
            )

    return PolicyResult(
        blocked=tuple(blocked),
        allowed=tuple(allowed),
        warnings=tuple(warnings),
    )


def run_pip_audit(requirement: Path) -> dict[str, Any]:
    """运行严格 pip-audit；漏洞导致的 exit 1 交由策略判断。"""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--strict",
            "--progress-spinner=off",
            "--format=json",
            "--requirement",
            str(requirement),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        summary = (result.stderr or result.stdout).strip()[:300]
        raise ValueError(f"pip-audit 未返回有效 JSON：{summary}") from exc
    if not isinstance(payload, dict):
        raise ValueError("pip-audit JSON 顶层必须是对象。")
    if result.returncode not in {0, 1}:
        summary = result.stderr.strip()[:300] or "unknown error"
        raise ValueError(f"pip-audit 执行失败：{summary}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="校验 Python production dependency audit policy。"
    )
    parser.add_argument(
        "--requirement",
        type=Path,
        default=repo_root / "backend/requirements.txt",
        help="需要审计的 requirements 文件。",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=repo_root / "security/pip-audit-exceptions.json",
        help="带到期日的安全例外 JSON。",
    )
    parser.add_argument(
        "--audit-json",
        type=Path,
        help="读取已有 pip-audit JSON，主要用于离线测试。",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=date.today(),
        help="覆盖策略日期，格式 YYYY-MM-DD。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """运行审计策略并返回 CI 友好的退出码。"""
    args = build_parser().parse_args(argv)
    try:
        if args.audit_json:
            audit_payload = json.loads(args.audit_json.read_text(encoding="utf-8"))
            if not isinstance(audit_payload, dict):
                raise ValueError("pip-audit JSON 顶层必须是对象。")
        else:
            audit_payload = run_pip_audit(args.requirement)
        findings = collect_findings(audit_payload)
        exceptions = load_exceptions(args.exceptions)
        result = evaluate_policy(findings, exceptions, today=args.today)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"pip-audit policy: ERROR\n- {exc}", file=sys.stderr)
        return 2

    for message in result.allowed:
        print(f"ALLOW: {message}")
    for message in result.warnings:
        print(f"WARN: {message}")
    for message in result.blocked:
        print(f"BLOCK: {message}", file=sys.stderr)
    if result.passed:
        print(
            "pip-audit policy: PASS "
            f"findings={len(findings)} exceptions={len(exceptions)}"
        )
        return 0
    print(
        "pip-audit policy: FAIL "
        f"blocked={len(result.blocked)} findings={len(findings)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
