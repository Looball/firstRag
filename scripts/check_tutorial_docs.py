#!/usr/bin/env python3
"""校验 FirstRAG 教程链接、结构、命令、素材和敏感占位符。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = Path("docs/tutorials/tutorial_manifest.json")
SUPPORTED_FIXTURE_ORIGINS = {"repository-authored-synthetic"}
SUPPORTED_FIXTURE_KINDS = {"markdown", "retrieval", "ocr-ground-truth"}
SHELL_LANGUAGES = {"bash", "sh", "shell", "zsh"}
LINK_PATTERN = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
REPOSITORY_PATH_PATTERN = re.compile(
    r"^(?:\.github|backend|deploy|docs|frontend|scripts)/[^\s]+$"
)
ROOT_FILE_PATTERN = re.compile(
    r"^(?:AGENTS\.md|README\.md|LICENSE|docker-compose\.yml|\.env\.example)$"
)
SCRIPT_REFERENCE_PATTERN = re.compile(
    r"(?<![\w./-])"
    r"((?:scripts|backend|frontend|deploy|docs)/"
    r"[A-Za-z0-9_./-]+\.(?:py|sh|json|ya?ml|md|txt|tsx?|css|sql))"
)
HIGH_RISK_SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\."
                   r"[A-Za-z0-9_-]{12,}\b"),
    ),
)


@dataclass(frozen=True)
class DocumentationViolation:
    """表示一条包含文件、行号和可操作原因的文档违规。"""

    path: Path
    line_number: int
    message: str

    def format(self, repository_root: Path) -> str:
        """格式化为适合本地和 CI 日志定位的单行文本。"""
        try:
            display_path = self.path.relative_to(repository_root)
        except ValueError:
            display_path = self.path
        return f"{display_path}:{self.line_number}: {self.message}"


@dataclass(frozen=True)
class MarkdownDocument:
    """保存教程 Markdown 正文、非代码行、heading 和 fenced block。"""

    path: Path
    lines: tuple[str, ...]
    prose_lines: tuple[tuple[int, str], ...]
    headings: dict[str, int]
    heading_titles: frozenset[str]
    shell_blocks: tuple[tuple[int, tuple[str, ...]], ...]
    fence_violations: tuple[DocumentationViolation, ...]


def _heading_slug(title: str) -> str:
    """按 GitHub 风格把 Unicode heading 转换为稳定 anchor。"""
    without_links = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    without_tags = re.sub(r"<[^>]+>", "", without_links)
    normalized: list[str] = []
    for character in without_tags.strip().lower():
        category = unicodedata.category(character)
        if character in {" ", "-", "_"} or category[0] in {"L", "N", "M"}:
            normalized.append(character)
    return "".join(normalized).replace(" ", "-")


def parse_markdown_document(path: Path) -> MarkdownDocument:
    """解析 heading、prose 和 shell fence，不执行 Markdown 渲染。"""
    lines = tuple(path.read_text(encoding="utf-8").splitlines())
    prose_lines: list[tuple[int, str]] = []
    headings: dict[str, int] = {}
    heading_titles: set[str] = set()
    shell_blocks: list[tuple[int, tuple[str, ...]]] = []
    fence_violations: list[DocumentationViolation] = []
    slug_counts: dict[str, int] = {}
    in_fence = False
    fence_marker = ""
    fence_language = ""
    fence_start = 0
    fence_lines: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        fence_match = re.match(r"^(`{3,}|~{3,})([^`]*)$", stripped)
        if fence_match is not None:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
                raw_language = fence_match.group(2).strip()
                fence_language = (
                    raw_language.split()[0].lower()
                    if raw_language
                    else ""
                )
                fence_start = line_number
                fence_lines = []
                continue
            if marker[0] == fence_marker:
                if fence_language in SHELL_LANGUAGES:
                    shell_blocks.append((fence_start, tuple(fence_lines)))
                in_fence = False
                fence_marker = ""
                fence_language = ""
                fence_lines = []
                continue

        if in_fence:
            fence_lines.append(line)
            continue

        prose_lines.append((line_number, line))
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading_match is None:
            continue
        title = heading_match.group(1).strip()
        heading_titles.add(title)
        base_slug = _heading_slug(title)
        duplicate_index = slug_counts.get(base_slug, 0)
        slug_counts[base_slug] = duplicate_index + 1
        slug = base_slug if duplicate_index == 0 else f"{base_slug}-{duplicate_index}"
        headings[slug] = line_number

    if in_fence:
        fence_violations.append(
            DocumentationViolation(path, fence_start, "代码块未闭合")
        )
    return MarkdownDocument(
        path=path,
        lines=lines,
        prose_lines=tuple(prose_lines),
        headings=headings,
        heading_titles=frozenset(heading_titles),
        shell_blocks=tuple(shell_blocks),
        fence_violations=tuple(fence_violations),
    )


def _parse_link_target(raw_target: str) -> tuple[str, str]:
    """把 Markdown target 拆成相对路径和可选 anchor。"""
    normalized = raw_target.strip()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1].strip()
    elif " " in normalized:
        normalized = normalized.split(maxsplit=1)[0]
    decoded = unquote(normalized)
    path_part, separator, fragment = decoded.partition("#")
    return path_part, fragment if separator else ""


def _resolve_repository_path(
    repository_root: Path,
    document_path: Path,
    target: str,
) -> Path:
    """把 repo-root 或 Markdown 相对路径解析为绝对路径。"""
    if target.startswith("/"):
        return (repository_root / target.lstrip("/")).resolve()
    return (document_path.parent / target).resolve()


def check_markdown_links(
    repository_root: Path,
    documents: dict[Path, MarkdownDocument],
) -> list[DocumentationViolation]:
    """校验教程内部文件目标和 heading anchor。"""
    violations: list[DocumentationViolation] = []
    for document in list(documents.values()):
        for line_number, line in document.prose_lines:
            for match in LINK_PATTERN.finditer(line):
                raw_target = match.group(1)
                if re.match(r"^(?:https?://|mailto:|data:)", raw_target):
                    continue
                target_path, fragment = _parse_link_target(raw_target)
                resolved_path = (
                    document.path
                    if not target_path
                    else _resolve_repository_path(
                        repository_root,
                        document.path,
                        target_path,
                    )
                )
                try:
                    resolved_path.relative_to(repository_root)
                except ValueError:
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            f"内部链接越出仓库：{raw_target}",
                        )
                    )
                    continue
                if not resolved_path.exists():
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            f"链接目标不存在：{raw_target}",
                        )
                    )
                    continue
                if not fragment or resolved_path.suffix.lower() != ".md":
                    continue
                target_document = documents.get(resolved_path)
                if target_document is None:
                    target_document = parse_markdown_document(resolved_path)
                if fragment not in target_document.headings:
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            f"章节 anchor 不存在：{raw_target}",
                        )
                    )
    return violations


def check_inline_repository_paths(
    repository_root: Path,
    documents: dict[Path, MarkdownDocument],
) -> list[DocumentationViolation]:
    """校验 inline code 中显式写出的 repo-root 源码路径。"""
    violations: list[DocumentationViolation] = []
    for document in documents.values():
        for line_number, line in document.prose_lines:
            for match in INLINE_CODE_PATTERN.finditer(line):
                value = match.group(1).strip().rstrip(".,;:，。；：")
                if any(character in value for character in "*{}$<>"):
                    continue
                if not (
                    REPOSITORY_PATH_PATTERN.fullmatch(value)
                    or ROOT_FILE_PATTERN.fullmatch(value)
                ):
                    continue
                resolved_path = (repository_root / value.rstrip("/")).resolve()
                if not resolved_path.exists():
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            f"源码路径不存在：{value}",
                        )
                    )
    return violations


def check_shell_blocks(
    repository_root: Path,
    documents: dict[Path, MarkdownDocument],
) -> list[DocumentationViolation]:
    """检查 copyable shell block 和其中引用的仓库文件。"""
    violations: list[DocumentationViolation] = []
    for document in documents.values():
        violations.extend(document.fence_violations)
        for fence_start, block_lines in document.shell_blocks:
            for offset, line in enumerate(block_lines, start=1):
                line_number = fence_start + offset
                if re.match(r"^\s*\$\s+", line):
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            "shell 命令不能包含不可复制的 prompt 前缀",
                        )
                    )
                if re.search(r"(?:^|\s)docker-compose(?=\s)", line):
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            "使用 Docker Compose v2 命令 `docker compose`，"
                            "不要使用 `docker-compose`",
                        )
                    )
                if re.search(r"\\\s+$", line) and not line.endswith("\\"):
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            "续行反斜杠后不能有空白字符",
                        )
                    )
                for reference in SCRIPT_REFERENCE_PATTERN.findall(line):
                    if not (repository_root / reference).exists():
                        violations.append(
                            DocumentationViolation(
                                document.path,
                                line_number,
                                f"命令引用的仓库路径不存在：{reference}",
                            )
                        )
    return violations


def check_sensitive_content(paths: list[Path]) -> list[DocumentationViolation]:
    """阻断教程和 fixture 中几类高置信度可用凭据模式。"""
    violations: list[DocumentationViolation] = []
    for path in paths:
        if path.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            for label, pattern in HIGH_RISK_SECRET_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        DocumentationViolation(
                            path,
                            line_number,
                            f"疑似可用敏感信息（{label}），请改用明显占位符",
                        )
                    )
    return violations


def check_forbidden_current_runtime_patterns(
    manifest_path: Path,
    manifest: dict[str, object],
    documents: dict[Path, MarkdownDocument],
) -> list[DocumentationViolation]:
    """拒绝教程把历史 Chroma 路径继续写成当前 runtime。"""
    raw_patterns = manifest.get("forbidden_current_runtime_patterns")
    if not isinstance(raw_patterns, list) or not raw_patterns or any(
        not isinstance(pattern, str) or not pattern
        for pattern in raw_patterns
    ):
        return [
            DocumentationViolation(
                manifest_path,
                1,
                "forbidden_current_runtime_patterns 必须是非空字符串数组",
            )
        ]

    violations: list[DocumentationViolation] = []
    for document in documents.values():
        for line_number, line in enumerate(document.lines, start=1):
            for pattern in raw_patterns:
                if pattern in line:
                    violations.append(
                        DocumentationViolation(
                            document.path,
                            line_number,
                            f"当前 Milvus 基线不应再出现 Chroma runtime 片段：{pattern}",
                        )
                    )
    return violations


def _load_manifest(path: Path) -> dict[str, object]:
    """读取教程 manifest，并生成简洁的格式错误。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"无法读取教程 manifest：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"教程 manifest 不是有效 JSON：{path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("教程 manifest schema_version 必须为 1")
    return payload


def check_manifest(
    repository_root: Path,
    manifest_path: Path,
    documents: dict[Path, MarkdownDocument],
) -> tuple[list[DocumentationViolation], list[Path]]:
    """校验核心章节、三级练习、索引、fixture 来源和 CI 接入。"""
    violations: list[DocumentationViolation] = []
    fixture_paths: list[Path] = []
    try:
        manifest = _load_manifest(manifest_path)
    except ValueError as exc:
        return [DocumentationViolation(manifest_path, 1, str(exc))], fixture_paths

    raw_index_path = manifest.get("index_path")
    raw_workflow_path = manifest.get("ci_workflow_path")
    raw_chapters = manifest.get("core_chapters")
    raw_fixtures = manifest.get("fixtures")
    if not isinstance(raw_index_path, str):
        violations.append(DocumentationViolation(manifest_path, 1, "index_path 缺失"))
        return violations, fixture_paths
    index_path = (repository_root / raw_index_path).resolve()
    if not index_path.is_file():
        violations.append(
            DocumentationViolation(manifest_path, 1, f"教程索引不存在：{raw_index_path}")
        )
        return violations, fixture_paths
    index_targets = {
        _resolve_repository_path(repository_root, index_path, _parse_link_target(match.group(1))[0])
        for line in index_path.read_text(encoding="utf-8").splitlines()
        for match in LINK_PATTERN.finditer(line)
        if _parse_link_target(match.group(1))[0]
        and not re.match(r"^(?:https?://|mailto:|data:)", match.group(1))
    }

    if not isinstance(raw_chapters, list) or not raw_chapters:
        violations.append(
            DocumentationViolation(
                manifest_path,
                1,
                "core_chapters 必须是非空数组",
            )
        )
    else:
        for item in raw_chapters:
            if not isinstance(item, dict):
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        "core_chapters 条目必须是对象",
                    )
                )
                continue
            chapter_value = item.get("path")
            chapter_title = item.get("title")
            required_headings = item.get("required_headings")
            credential_free_heading = item.get("credential_free_heading")
            if not isinstance(chapter_value, str):
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        "核心章节 path 缺失",
                    )
                )
                continue
            chapter_path = (repository_root / chapter_value).resolve()
            if not chapter_path.is_file():
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"核心章节不存在：{chapter_value}",
                    )
                )
                continue
            if chapter_path not in index_targets:
                violations.append(
                    DocumentationViolation(
                        index_path,
                        1,
                        f"教程索引未链接核心章节：{chapter_value}",
                    )
                )
            chapter_document = documents.get(chapter_path) or parse_markdown_document(chapter_path)
            documents[chapter_path] = chapter_document
            if (
                not isinstance(chapter_title, str)
                or chapter_title not in chapter_document.heading_titles
            ):
                violations.append(
                    DocumentationViolation(
                        chapter_path,
                        1,
                        f"核心章节缺少 manifest 声明的标题：{chapter_title}",
                    )
                )
            if not isinstance(required_headings, list) or any(
                not isinstance(heading, str) for heading in required_headings
            ):
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"{chapter_value} required_headings 无效",
                    )
                )
                continue
            for heading in required_headings:
                if heading not in chapter_document.heading_titles:
                    violations.append(
                        DocumentationViolation(
                            chapter_path,
                            1,
                            f"核心章节缺少 manifest 声明的 heading：{heading}",
                        )
                    )
            if credential_free_heading not in required_headings:
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"{chapter_value} credential_free_heading 必须属于 required_headings",
                    )
                )

    if not isinstance(raw_fixtures, list) or not raw_fixtures:
        violations.append(
            DocumentationViolation(
                manifest_path,
                1,
                "fixtures 必须是非空数组",
            )
        )
    else:
        for item in raw_fixtures:
            if not isinstance(item, dict):
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        "fixtures 条目必须是对象",
                    )
                )
                continue
            fixture_value = item.get("path")
            fixture_kind = item.get("kind")
            fixture_origin = item.get("origin")
            if not isinstance(fixture_value, str):
                violations.append(DocumentationViolation(manifest_path, 1, "fixture path 缺失"))
                continue
            fixture_path = (repository_root / fixture_value).resolve()
            fixture_paths.append(fixture_path)
            if not fixture_path.is_file():
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"教程 fixture 不存在：{fixture_value}",
                    )
                )
            if fixture_kind not in SUPPORTED_FIXTURE_KINDS:
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"fixture kind 不受支持：{fixture_kind}",
                    )
                )
            if fixture_origin not in SUPPORTED_FIXTURE_ORIGINS:
                violations.append(
                    DocumentationViolation(
                        manifest_path,
                        1,
                        f"fixture origin 不受支持：{fixture_origin}",
                    )
                )

    if not isinstance(raw_workflow_path, str):
        violations.append(DocumentationViolation(manifest_path, 1, "ci_workflow_path 缺失"))
    else:
        workflow_path = (repository_root / raw_workflow_path).resolve()
        if not workflow_path.is_file():
            violations.append(
                DocumentationViolation(
                    manifest_path,
                    1,
                    f"CI workflow 不存在：{raw_workflow_path}",
                )
            )
        elif (
            "run: python3 scripts/check_tutorial_docs.py"
            not in workflow_path.read_text(encoding="utf-8")
        ):
            violations.append(
                DocumentationViolation(
                    workflow_path,
                    1,
                    "CI 未执行 `python3 scripts/check_tutorial_docs.py`",
                )
            )
    return violations, fixture_paths


def collect_violations(
    repository_root: Path,
    manifest_relative_path: Path = DEFAULT_MANIFEST_PATH,
) -> list[DocumentationViolation]:
    """收集仓库教程的全部稳定、可定位违规。"""
    resolved_root = repository_root.resolve()
    tutorial_root = resolved_root / "docs/tutorials"
    manifest_path = (resolved_root / manifest_relative_path).resolve()
    markdown_paths = (
        sorted(tutorial_root.rglob("*.md"))
        if tutorial_root.is_dir()
        else []
    )
    documents = {
        path.resolve(): parse_markdown_document(path.resolve())
        for path in markdown_paths
    }
    violations, fixture_paths = check_manifest(
        resolved_root,
        manifest_path,
        documents,
    )
    try:
        manifest = _load_manifest(manifest_path)
    except ValueError:
        manifest = {}
    violations.extend(
        check_forbidden_current_runtime_patterns(
            manifest_path,
            manifest,
            documents,
        )
    )
    violations.extend(check_markdown_links(resolved_root, documents))
    violations.extend(check_inline_repository_paths(resolved_root, documents))
    violations.extend(check_shell_blocks(resolved_root, documents))
    sensitive_paths = sorted(set(markdown_paths + fixture_paths + [manifest_path]))
    existing_sensitive_paths = [path for path in sensitive_paths if path.is_file()]
    violations.extend(check_sensitive_content(existing_sensitive_paths))
    return sorted(
        violations,
        key=lambda item: (str(item.path), item.line_number, item.message),
    )


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    parser = argparse.ArgumentParser(
        description="检查 FirstRAG 教程链接、源码路径、练习、素材和 CI 接入。"
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="仓库根目录，默认自动从脚本位置解析。",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="相对仓库根目录的教程 manifest。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行教程文档检查并返回 CI 友好的退出码。"""
    args = build_parser().parse_args(argv)
    violations = collect_violations(args.repository_root, args.manifest)
    for violation in violations:
        print(
            f"BLOCK: {violation.format(args.repository_root.resolve())}",
            file=sys.stderr,
        )
    if violations:
        print(
            f"Tutorial docs check: FAIL violations={len(violations)}",
            file=sys.stderr,
        )
        return 1
    tutorial_count = len(
        list((args.repository_root / "docs/tutorials").rglob("*.md"))
    )
    print(f"Tutorial docs check: PASS markdown_files={tutorial_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
