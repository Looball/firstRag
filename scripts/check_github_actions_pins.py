"""检查 GitHub workflow 中的外部 Action 是否固定到完整 commit SHA。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


USES_PATTERN = re.compile(
    r"^\s*(?:-\s*)?uses:\s*[\"']?([^\"'#\s]+)[\"']?"
    r"\s*(?:#\s*(.*))?$"
)
FULL_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
VERSION_COMMENT_PATTERN = re.compile(r"^v\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class ActionReference:
    """表示 workflow 中一条外部 Action 引用。"""

    path: Path
    line_number: int
    action: str
    reference: str
    version_comment: str


def _workflow_files(paths: list[Path]) -> list[Path]:
    """返回给定文件或目录下稳定排序的 workflow YAML。"""
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix in {".yml", ".yaml"}:
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob("*.yml"))
            files.update(path.rglob("*.yaml"))
    return sorted(files)


def collect_action_references(paths: list[Path]) -> list[ActionReference]:
    """收集非本地、非 Docker 的 GitHub Action 引用。"""
    references: list[ActionReference] = []
    for path in _workflow_files(paths):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = USES_PATTERN.match(line)
            if match is None:
                continue
            value = match.group(1)
            if value.startswith("./") or value.startswith("docker://"):
                continue
            action, separator, reference = value.rpartition("@")
            references.append(
                ActionReference(
                    path=path,
                    line_number=line_number,
                    action=action if separator else value,
                    reference=reference if separator else "",
                    version_comment=(match.group(2) or "").strip(),
                )
            )
    return references


def validate_action_references(
    references: list[ActionReference],
) -> list[str]:
    """返回所有 tag、branch、短 SHA 和缺失版本注释的问题。"""
    violations: list[str] = []
    for item in references:
        location = f"{item.path}:{item.line_number}"
        if not item.action or not FULL_SHA_PATTERN.fullmatch(item.reference):
            violations.append(
                f"{location}: {item.action or 'unknown action'} 必须固定到 40 位 commit SHA"
            )
            continue
        if not VERSION_COMMENT_PATTERN.fullmatch(item.version_comment):
            violations.append(
                f"{location}: {item.action} 必须保留同一行 release tag 注释，"
                "例如 # v6.0.2"
            )
    return violations


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="校验所有外部 GitHub Action 都固定到完整 commit SHA。"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[repo_root / ".github/workflows", repo_root / ".github/actions"],
        help="需要扫描的 workflow 文件或目录。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行 GitHub Actions pin policy 并返回 CI 友好的退出码。"""
    args = build_parser().parse_args(argv)
    references = collect_action_references(args.paths)
    violations = validate_action_references(references)
    for violation in violations:
        print(f"BLOCK: {violation}", file=sys.stderr)
    if violations:
        print(
            "GitHub Actions pin policy: FAIL "
            f"references={len(references)} violations={len(violations)}",
            file=sys.stderr,
        )
        return 1
    print(f"GitHub Actions pin policy: PASS references={len(references)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
