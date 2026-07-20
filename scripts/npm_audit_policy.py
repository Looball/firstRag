"""执行 npm production dependency 审计并校验限时安全例外。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}
BLOCK_WITHOUT_EXCEPTION = SEVERITY_RANK["moderate"]
UNEXEMPTABLE_SEVERITY = SEVERITY_RANK["high"]
MAX_EXCEPTION_DAYS = 31


@dataclass(frozen=True)
class AuditFinding:
    """表示 npm audit 中的一条实际 advisory。"""

    advisory_id: str
    package: str
    severity: str
    title: str
    url: str


@dataclass(frozen=True)
class AuditException:
    """表示经过审查、带到期日的 moderate advisory 例外。"""

    advisory_id: str
    package: str
    severity: str
    reviewed_on: date
    expires_on: date
    reason: str


@dataclass(frozen=True)
class PolicyResult:
    """保存审计策略判断结果。"""

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


def _advisory_id(via: dict[str, Any]) -> str:
    """优先从 GitHub advisory URL 提取稳定 ID。"""
    url = str(via.get("url") or "").strip()
    if url:
        path_name = Path(urlparse(url).path).name.strip()
        if path_name:
            return path_name.upper()
    source = str(via.get("source") or "").strip()
    return f"NPM-{source}" if source else ""


def collect_findings(payload: dict[str, Any]) -> list[AuditFinding]:
    """从 npm audit JSON 中提取并去重实际 advisory。"""
    vulnerabilities = payload.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        raise ValueError("npm audit JSON 缺少 vulnerabilities 对象。")

    findings: dict[tuple[str, str], AuditFinding] = {}
    for package_name, vulnerability in vulnerabilities.items():
        if not isinstance(vulnerability, dict):
            continue
        via_items = vulnerability.get("via") or []
        if not isinstance(via_items, list):
            continue
        direct_advisory_found = False
        for via in via_items:
            if not isinstance(via, dict):
                continue
            advisory_id = _advisory_id(via)
            if not advisory_id:
                continue
            direct_advisory_found = True
            package = str(via.get("name") or package_name).strip()
            severity = str(
                via.get("severity") or vulnerability.get("severity") or ""
            ).strip().lower()
            if severity not in SEVERITY_RANK:
                raise ValueError(
                    f"advisory {advisory_id} 的 severity 无效：{severity or '缺失'}。"
                )
            finding = AuditFinding(
                advisory_id=advisory_id,
                package=package,
                severity=severity,
                title=str(via.get("title") or advisory_id).strip(),
                url=str(via.get("url") or "").strip(),
            )
            findings[(finding.advisory_id, finding.package)] = finding

        vulnerability_severity = str(
            vulnerability.get("severity") or ""
        ).strip().lower()
        if (
            not direct_advisory_found
            and SEVERITY_RANK.get(vulnerability_severity, -1)
            >= UNEXEMPTABLE_SEVERITY
        ):
            # npm 通常会在依赖叶子节点给出 advisory 对象；若只有字符串传播链，
            # 仍需保守阻断 high/critical，不能因缺少 advisory URL 被漏检。
            synthetic_id = (
                "NPM-PACKAGE-"
                + str(package_name).upper().replace("@", "").replace("/", "-")
            )
            finding = AuditFinding(
                advisory_id=synthetic_id,
                package=str(package_name),
                severity=vulnerability_severity,
                title="npm audit reported high/critical dependency chain",
                url="",
            )
            findings[(finding.advisory_id, finding.package)] = finding

    return sorted(
        findings.values(),
        key=lambda item: (
            -SEVERITY_RANK[item.severity],
            item.advisory_id,
            item.package,
        ),
    )


def load_exceptions(path: Path) -> list[AuditException]:
    """读取并严格校验安全例外清单。"""
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
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_exceptions):
        if not isinstance(item, dict):
            raise ValueError(f"exceptions[{index}] 必须是对象。")
        advisory_id = str(item.get("advisory_id") or "").strip().upper()
        package = str(item.get("package") or "").strip()
        severity = str(item.get("severity") or "").strip().lower()
        reason = str(item.get("reason") or "").strip()
        if not advisory_id or not package or not reason:
            raise ValueError(
                f"exceptions[{index}] 必须包含 advisory_id、package 和 reason。"
            )
        if severity not in SEVERITY_RANK:
            raise ValueError(f"exceptions[{index}] 的 severity 无效。")
        if SEVERITY_RANK[severity] >= UNEXEMPTABLE_SEVERITY:
            raise ValueError("high/critical advisory 禁止加入例外清单。")
        reviewed_on = _parse_iso_date(item.get("reviewed_on"), "reviewed_on")
        expires_on = _parse_iso_date(item.get("expires_on"), "expires_on")
        if expires_on < reviewed_on:
            raise ValueError("expires_on 不能早于 reviewed_on。")
        if (expires_on - reviewed_on).days > MAX_EXCEPTION_DAYS:
            raise ValueError(
                f"安全例外有效期不能超过 {MAX_EXCEPTION_DAYS} 天。"
            )
        key = (advisory_id, package)
        if key in seen:
            raise ValueError(f"安全例外重复：{advisory_id} / {package}。")
        seen.add(key)
        exceptions.append(
            AuditException(
                advisory_id=advisory_id,
                package=package,
                severity=severity,
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
    """执行 high/critical 强阻断和 moderate 限时例外策略。"""
    exception_map = {
        (item.advisory_id, item.package): item
        for item in exceptions
    }
    active_finding_keys = {
        (item.advisory_id, item.package)
        for item in findings
    }
    blocked: list[str] = []
    allowed: list[str] = []
    warnings: list[str] = []

    for finding in findings:
        label = (
            f"{finding.severity} {finding.advisory_id} "
            f"package={finding.package}"
        )
        severity_rank = SEVERITY_RANK[finding.severity]
        exception = exception_map.get(
            (finding.advisory_id, finding.package)
        )

        if exception is not None and exception.severity != finding.severity:
            blocked.append(
                f"例外 severity 不匹配：{label} "
                f"exception={exception.severity}"
            )
            continue
        if severity_rank >= UNEXEMPTABLE_SEVERITY:
            blocked.append(f"禁止例外的漏洞：{label}")
            continue
        if severity_rank < BLOCK_WITHOUT_EXCEPTION:
            warnings.append(f"低于阻断阈值：{label}")
            continue
        if exception is None:
            blocked.append(f"未登记的漏洞：{label}")
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
        allowed.append(
            f"限时例外：{label} expires_on={exception.expires_on}"
        )
        if (exception.expires_on - today).days <= 7:
            warnings.append(
                f"安全例外将在 7 天内到期：{finding.advisory_id} "
                f"expires_on={exception.expires_on}"
            )

    for exception in exceptions:
        key = (exception.advisory_id, exception.package)
        if key not in active_finding_keys:
            blocked.append(
                "安全例外已无对应漏洞，请删除："
                f"{exception.advisory_id} package={exception.package}"
            )

    return PolicyResult(
        blocked=tuple(blocked),
        allowed=tuple(allowed),
        warnings=tuple(warnings),
    )


def run_npm_audit(working_directory: Path) -> dict[str, Any]:
    """运行 production npm audit；漏洞导致的 exit 1 交由策略判断。"""
    result = subprocess.run(
        ["npm", "audit", "--omit=dev", "--json"],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        summary = (result.stderr or result.stdout).strip()[:300]
        raise ValueError(f"npm audit 未返回有效 JSON：{summary}") from exc
    if not isinstance(payload, dict):
        raise ValueError("npm audit JSON 顶层必须是对象。")
    if result.returncode not in {0, 1} or payload.get("error"):
        error = payload.get("error") or result.stderr.strip() or "unknown error"
        raise ValueError(f"npm audit 执行失败：{error}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="校验 npm production dependency audit policy。"
    )
    parser.add_argument(
        "--working-directory",
        type=Path,
        default=repo_root / "frontend",
        help="运行 npm audit 的目录，默认 frontend。",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=repo_root / "security/npm-audit-exceptions.json",
        help="带到期日的安全例外 JSON。",
    )
    parser.add_argument(
        "--audit-json",
        type=Path,
        help="读取已有 npm audit JSON，主要用于离线测试。",
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
            audit_payload = json.loads(
                args.audit_json.read_text(encoding="utf-8")
            )
            if not isinstance(audit_payload, dict):
                raise ValueError("npm audit JSON 顶层必须是对象。")
        else:
            audit_payload = run_npm_audit(args.working_directory)
        findings = collect_findings(audit_payload)
        exceptions = load_exceptions(args.exceptions)
        result = evaluate_policy(findings, exceptions, today=args.today)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"npm audit policy: ERROR\n- {exc}", file=sys.stderr)
        return 2

    for message in result.allowed:
        print(f"ALLOW: {message}")
    for message in result.warnings:
        print(f"WARN: {message}")
    for message in result.blocked:
        print(f"BLOCK: {message}", file=sys.stderr)
    if result.passed:
        print(
            "npm audit policy: PASS "
            f"findings={len(findings)} exceptions={len(exceptions)}"
        )
        return 0
    print(
        "npm audit policy: FAIL "
        f"blocked={len(result.blocked)} findings={len(findings)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
