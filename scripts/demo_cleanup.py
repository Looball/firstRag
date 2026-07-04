#!/usr/bin/env python3
"""FirstRAG 在线 demo 数据清理脚本。"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_UPLOADS_DIR = PROJECT_ROOT / "uploads"
DEFAULT_VECTOR_STORE_PATH = PROJECT_ROOT / "vector_db/chroma"
DEFAULT_CHROMA_COLLECTION_NAME = "langchain"
DEFAULT_CONFIRM_TEXT = "cleanup-demo-data"
APP_UPLOADS_PREFIX = Path("/app/uploads")

Row = dict[str, Any]


class DemoCleanupError(RuntimeError):
    """demo 清理过程中的可预期错误。"""


@dataclass(frozen=True)
class DatabaseSnapshot:
    """清理计划需要读取的数据库元数据快照。"""

    users: list[Row]
    knowledge_bases: list[Row]
    knowledge_files: list[Row]
    knowledge_base_files: list[Row]
    conversations: list[Row]


@dataclass(frozen=True)
class RetentionConfig:
    """用户指定的保留与清理边界。"""

    retain_user_ids: set[int]
    retain_knowledge_base_ids: set[str]
    retain_file_ids: set[str]
    cleanup_user_ids: set[int]
    cutoff: datetime


@dataclass(frozen=True)
class CleanupSelection:
    """根据保留边界推导出的待清理对象 ID。"""

    cleanup_user_ids: set[int]
    cleanup_knowledge_base_ids: set[str]
    cleanup_file_ids: set[str]
    cleanup_conversation_ids: set[str]
    retained_user_ids: set[int]
    retained_knowledge_base_ids: set[str]
    retained_file_ids: set[str]


@dataclass(frozen=True)
class UploadCleanupTarget:
    """一个可安全删除的上传文件路径。"""

    file_id: str
    storage_path: str
    resolved_path: Path
    size_bytes: int


@dataclass(frozen=True)
class SkippedUploadTarget:
    """因路径越界或不可解析而跳过的上传文件。"""

    file_id: str
    storage_path: str
    reason: str


@dataclass(frozen=True)
class VectorCleanupResult:
    """Chroma 单个 collection 的清理统计。"""

    collection_name: str
    file_id: str
    user_id: int
    matched_count: int
    deleted_count: int


@dataclass(frozen=True)
class CleanupPlan:
    """完整清理计划。"""

    cutoff: datetime
    selection: CleanupSelection
    counts: dict[str, int]
    upload_targets: list[UploadCleanupTarget]
    skipped_upload_targets: list[SkippedUploadTarget]
    vector_results: list[VectorCleanupResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_arg_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=(
            "Clean temporary FirstRAG demo data. The default mode is dry-run."
        ),
    )
    parser.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL, then COMPOSE_DATABASE_URL.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Dotenv file used to load runtime configuration.",
    )
    parser.add_argument(
        "--uploads-dir",
        type=Path,
        help="Host/container uploads root. Defaults to UPLOADS_DIR or ./uploads.",
    )
    parser.add_argument(
        "--vector-store-path",
        type=Path,
        help=(
            "Chroma persist directory. Defaults to VECTOR_STORE_PATH, "
            "then VECTOR_DB_DIR/chroma, then ./vector_db/chroma."
        ),
    )
    parser.add_argument(
        "--chroma-collection-name",
        default=None,
        help="Base Chroma collection name. Defaults to CHROMA_COLLECTION_NAME.",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=7,
        help="Clean non-retained demo data created before this age in days.",
    )
    parser.add_argument(
        "--retain-user",
        action="append",
        default=[],
        help="Username to retain. Can be specified multiple times.",
    )
    parser.add_argument(
        "--retain-user-id",
        type=int,
        action="append",
        default=[],
        help="User id to retain. Can be specified multiple times.",
    )
    parser.add_argument(
        "--retain-knowledge-base-id",
        action="append",
        default=[],
        help="Knowledge base UUID to retain. Its linked files are retained too.",
    )
    parser.add_argument(
        "--retain-file-id",
        action="append",
        default=[],
        help="Knowledge file UUID to retain. Can be specified multiple times.",
    )
    parser.add_argument(
        "--cleanup-user",
        action="append",
        default=[],
        help="Username to clean regardless of age, unless retained.",
    )
    parser.add_argument(
        "--cleanup-user-id",
        type=int,
        action="append",
        default=[],
        help="User id to clean regardless of age, unless retained.",
    )
    parser.add_argument(
        "--skip-chroma",
        action="store_true",
        help="Skip Chroma entry counting/deletion. PostgreSQL/uploads still run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the cleanup plan only. This is already the default mode.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply the cleanup plan. Requires --confirm cleanup-demo-data.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Execution guard. Must equal {DEFAULT_CONFIRM_TEXT!r}.",
    )
    return parser


def normalize_env_value(raw_value: str) -> str:
    """移除 dotenv 值两侧空白和一层引号。"""
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(env_file: Path) -> dict[str, str]:
    """读取 dotenv 文件，不执行 shell 语法，也不输出配置值。"""
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        values[key] = normalize_env_value(raw_value)
    return values


def build_runtime_env(env_file: Path) -> dict[str, str]:
    """合并 dotenv 与当前进程环境，进程环境优先。"""
    env = load_env_file(env_file)
    env.update(os.environ)
    return env


def resolve_project_path(value: str | os.PathLike[str], default: Path) -> Path:
    """将相对路径统一解析到项目根目录。"""
    raw_path = Path(value or default)
    return raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path


def resolve_uploads_dir(args: argparse.Namespace, env: Mapping[str, str]) -> Path:
    """解析本次清理使用的上传根目录。"""
    if args.uploads_dir is not None:
        return resolve_project_path(args.uploads_dir, DEFAULT_UPLOADS_DIR)

    env_uploads_dir = env.get("UPLOADS_DIR", "")
    return resolve_project_path(env_uploads_dir, DEFAULT_UPLOADS_DIR)


def resolve_vector_store_path(
    args: argparse.Namespace,
    env: Mapping[str, str],
) -> Path:
    """解析 Chroma 持久化目录。"""
    if args.vector_store_path is not None:
        return resolve_project_path(
            args.vector_store_path,
            DEFAULT_VECTOR_STORE_PATH,
        )

    vector_store_path = env.get("VECTOR_STORE_PATH", "")
    if vector_store_path:
        return resolve_project_path(vector_store_path, DEFAULT_VECTOR_STORE_PATH)

    vector_db_dir = env.get("VECTOR_DB_DIR", "")
    if vector_db_dir:
        return resolve_project_path(vector_db_dir, PROJECT_ROOT / "vector_db") / "chroma"

    return DEFAULT_VECTOR_STORE_PATH


def load_database_url(
    explicit_database_url: str | None,
    env: Mapping[str, str],
) -> str:
    """读取数据库连接串，不向 stdout/stderr 输出敏感内容。"""
    if explicit_database_url:
        return explicit_database_url

    database_url = env.get("DATABASE_URL") or env.get("COMPOSE_DATABASE_URL")
    if not database_url:
        raise DemoCleanupError(
            "缺少数据库连接配置，请设置 DATABASE_URL 或传入 --database-url。"
        )
    return database_url


def parse_uuid_set(raw_values: Sequence[str], option_name: str) -> set[str]:
    """校验并规范化 UUID 参数。"""
    normalized: set[str] = set()
    for raw_value in raw_values:
        try:
            normalized.add(str(UUID(raw_value)))
        except ValueError as exc:
            raise DemoCleanupError(
                f"{option_name} 需要使用合法 UUID：{raw_value}"
            ) from exc
    return normalized


def connect_database(database_url: str):
    """创建 PostgreSQL 连接。"""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - 依赖缺失时才触发。
        raise DemoCleanupError(
            "缺少 psycopg 依赖，请先安装 backend/requirements.txt。"
        ) from exc

    try:
        return psycopg.connect(database_url, row_factory=dict_row)
    except Exception as exc:  # pragma: no cover - 真实连接错误由集成环境覆盖。
        raise DemoCleanupError(
            "连接数据库失败，请检查 DATABASE_URL 和数据库服务状态。"
        ) from exc


def fetch_all(connection, sql: str, params: Sequence[Any] = ()) -> list[Row]:
    """执行查询并返回字典行列表。"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def fetch_count(connection, sql: str, params: Sequence[Any] = ()) -> int:
    """执行 COUNT 查询并返回整数。"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return int(row["count"] if isinstance(row, dict) else row[0])


def load_database_snapshot(connection) -> DatabaseSnapshot:
    """读取清理计划所需的非敏感数据库元数据。"""
    return DatabaseSnapshot(
        users=fetch_all(
            connection,
            """
            SELECT id, username, created_at
            FROM users
            ORDER BY id;
            """,
        ),
        knowledge_bases=fetch_all(
            connection,
            """
            SELECT id, user_id, name, is_default, created_at, deleted_at
            FROM knowledge_bases
            ORDER BY created_at, id;
            """,
        ),
        knowledge_files=fetch_all(
            connection,
            """
            SELECT
                id,
                user_id,
                original_name,
                storage_path,
                size_bytes,
                status,
                created_at,
                deleted_at
            FROM knowledge_files
            ORDER BY created_at, id;
            """,
        ),
        knowledge_base_files=fetch_all(
            connection,
            """
            SELECT knowledge_base_id, knowledge_file_id, created_at
            FROM knowledge_base_files;
            """,
        ),
        conversations=fetch_all(
            connection,
            """
            SELECT id, user_id, knowledge_base_id, title, created_at, deleted_at
            FROM conversations
            ORDER BY created_at, id;
            """,
        ),
    )


def resolve_usernames(
    snapshot: DatabaseSnapshot,
    usernames: Sequence[str],
    option_name: str,
) -> set[int]:
    """将用户名参数解析为用户 ID。"""
    if not usernames:
        return set()

    username_to_id = {
        str(user["username"]): int(user["id"])
        for user in snapshot.users
    }
    missing = sorted(set(usernames) - set(username_to_id))
    if missing:
        raise DemoCleanupError(
            f"{option_name} 指定的用户不存在：{', '.join(missing)}"
        )
    return {username_to_id[username] for username in usernames}


def normalize_uuid(value: Any) -> str:
    """将数据库中的 UUID 值规范化为字符串。"""
    return str(value)


def normalize_datetime(value: Any) -> datetime:
    """将数据库时间值转换为带时区的 datetime。"""
    if not isinstance(value, datetime):
        raise DemoCleanupError(f"无法解析数据库时间值：{value!r}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def created_before(row: Mapping[str, Any], cutoff: datetime) -> bool:
    """判断一行记录是否早于清理时间线。"""
    return normalize_datetime(row["created_at"]) < cutoff


def build_cleanup_selection(
    snapshot: DatabaseSnapshot,
    retention: RetentionConfig,
) -> CleanupSelection:
    """根据数据库快照和保留配置推导清理对象。"""
    user_ids = {int(user["id"]) for user in snapshot.users}
    kb_owner_by_id = {
        normalize_uuid(kb["id"]): int(kb["user_id"])
        for kb in snapshot.knowledge_bases
    }
    file_owner_by_id = {
        normalize_uuid(file_row["id"]): int(file_row["user_id"])
        for file_row in snapshot.knowledge_files
    }
    files_by_retained_kb: set[str] = {
        normalize_uuid(relation["knowledge_file_id"])
        for relation in snapshot.knowledge_base_files
        if normalize_uuid(relation["knowledge_base_id"])
        in retention.retain_knowledge_base_ids
    }

    missing_kb_ids = retention.retain_knowledge_base_ids - set(kb_owner_by_id)
    if missing_kb_ids:
        raise DemoCleanupError(
            "保留知识库不存在："
            f"{', '.join(sorted(missing_kb_ids))}"
        )

    explicit_retain_file_ids = set(retention.retain_file_ids)
    retained_file_ids = explicit_retain_file_ids | files_by_retained_kb
    missing_file_ids = explicit_retain_file_ids - set(file_owner_by_id)
    if missing_file_ids:
        raise DemoCleanupError(
            "保留文件不存在："
            f"{', '.join(sorted(missing_file_ids))}"
        )

    retained_user_ids = set(retention.retain_user_ids)
    retained_user_ids.update(
        kb_owner_by_id[kb_id]
        for kb_id in retention.retain_knowledge_base_ids
    )
    retained_user_ids.update(
        file_owner_by_id[file_id]
        for file_id in retained_file_ids
        if file_id in file_owner_by_id
    )

    missing_user_ids = retained_user_ids - user_ids
    if missing_user_ids:
        raise DemoCleanupError(
            "保留用户不存在："
            f"{', '.join(str(user_id) for user_id in sorted(missing_user_ids))}"
        )

    missing_cleanup_user_ids = retention.cleanup_user_ids - user_ids
    if missing_cleanup_user_ids:
        raise DemoCleanupError(
            "清理用户不存在："
            f"{', '.join(str(user_id) for user_id in sorted(missing_cleanup_user_ids))}"
        )

    conflicting_user_ids = retained_user_ids & retention.cleanup_user_ids
    if conflicting_user_ids:
        raise DemoCleanupError(
            "同一用户不能同时保留和显式清理："
            f"{', '.join(str(user_id) for user_id in sorted(conflicting_user_ids))}"
        )

    cleanup_user_ids = set(retention.cleanup_user_ids)
    for user in snapshot.users:
        user_id = int(user["id"])
        if user_id in retained_user_ids:
            continue
        if user_id in retention.cleanup_user_ids or created_before(
            user,
            retention.cutoff,
        ):
            cleanup_user_ids.add(user_id)

    cleanup_knowledge_base_ids: set[str] = set()
    for kb in snapshot.knowledge_bases:
        kb_id = normalize_uuid(kb["id"])
        user_id = int(kb["user_id"])
        if kb_id in retention.retain_knowledge_base_ids:
            continue
        if user_id in cleanup_user_ids:
            cleanup_knowledge_base_ids.add(kb_id)
            continue
        if user_id in retained_user_ids and created_before(kb, retention.cutoff):
            cleanup_knowledge_base_ids.add(kb_id)

    retained_file_ids = retained_file_ids | {
        normalize_uuid(relation["knowledge_file_id"])
        for relation in snapshot.knowledge_base_files
        if normalize_uuid(relation["knowledge_base_id"])
        in retention.retain_knowledge_base_ids
    }

    cleanup_file_ids: set[str] = set()
    for file_row in snapshot.knowledge_files:
        file_id = normalize_uuid(file_row["id"])
        user_id = int(file_row["user_id"])
        if file_id in retained_file_ids:
            continue
        if user_id in cleanup_user_ids:
            cleanup_file_ids.add(file_id)
            continue
        if user_id in retained_user_ids and created_before(
            file_row,
            retention.cutoff,
        ):
            cleanup_file_ids.add(file_id)

    cleanup_conversation_ids: set[str] = set()
    for conversation in snapshot.conversations:
        conversation_id = normalize_uuid(conversation["id"])
        user_id = int(conversation["user_id"])
        knowledge_base_id = normalize_uuid(conversation["knowledge_base_id"])
        if (
            user_id in cleanup_user_ids
            or knowledge_base_id in cleanup_knowledge_base_ids
        ):
            cleanup_conversation_ids.add(conversation_id)
            continue
        if user_id in retained_user_ids and created_before(
            conversation,
            retention.cutoff,
        ):
            cleanup_conversation_ids.add(conversation_id)

    return CleanupSelection(
        cleanup_user_ids=cleanup_user_ids,
        cleanup_knowledge_base_ids=cleanup_knowledge_base_ids,
        cleanup_file_ids=cleanup_file_ids,
        cleanup_conversation_ids=cleanup_conversation_ids,
        retained_user_ids=retained_user_ids,
        retained_knowledge_base_ids=set(retention.retain_knowledge_base_ids),
        retained_file_ids=retained_file_ids,
    )


def list_candidate_files(
    snapshot: DatabaseSnapshot,
    cleanup_file_ids: set[str],
) -> list[Row]:
    """返回待清理文件记录。"""
    return [
        file_row
        for file_row in snapshot.knowledge_files
        if normalize_uuid(file_row["id"]) in cleanup_file_ids
    ]


def is_relative_to(path: Path, parent: Path) -> bool:
    """兼容旧 Python 版本的 Path.is_relative_to。"""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_upload_target_path(
    storage_path: str,
    uploads_dir: Path,
    project_uploads_dir: Path = DEFAULT_UPLOADS_DIR,
) -> tuple[Path | None, str | None]:
    """将数据库 storage_path 映射到可安全删除的本地路径。"""
    uploads_root = uploads_dir.resolve()
    raw_path = Path(storage_path)

    if not raw_path.is_absolute():
        candidate = (PROJECT_ROOT / raw_path).resolve()
        if is_relative_to(candidate, uploads_root):
            return candidate, None
        candidate = (uploads_root / raw_path).resolve()
        if is_relative_to(candidate, uploads_root):
            return candidate, None
        return None, "相对路径不在 uploads 根目录内"

    absolute_path = raw_path.resolve()
    if is_relative_to(absolute_path, uploads_root):
        return absolute_path, None

    known_prefixes = [
        APP_UPLOADS_PREFIX,
        project_uploads_dir,
    ]
    for prefix in known_prefixes:
        prefix_path = prefix.resolve() if prefix != APP_UPLOADS_PREFIX else prefix
        try:
            relative = absolute_path.relative_to(prefix_path)
        except ValueError:
            continue

        candidate = (uploads_root / relative).resolve()
        if is_relative_to(candidate, uploads_root):
            return candidate, None

    return None, "路径不在配置的 uploads 根目录内"


def build_upload_targets(
    files: Sequence[Row],
    uploads_dir: Path,
) -> tuple[list[UploadCleanupTarget], list[SkippedUploadTarget]]:
    """根据文件 metadata 构建上传文件删除目标。"""
    targets: list[UploadCleanupTarget] = []
    skipped: list[SkippedUploadTarget] = []
    for file_row in files:
        file_id = normalize_uuid(file_row["id"])
        storage_path = str(file_row["storage_path"])
        resolved_path, reason = resolve_upload_target_path(storage_path, uploads_dir)
        if resolved_path is None:
            skipped.append(
                SkippedUploadTarget(
                    file_id=file_id,
                    storage_path=storage_path,
                    reason=reason or "路径不可解析",
                )
            )
            continue

        size_bytes = 0
        if resolved_path.exists() and resolved_path.is_file():
            size_bytes = resolved_path.stat().st_size
        targets.append(
            UploadCleanupTarget(
                file_id=file_id,
                storage_path=storage_path,
                resolved_path=resolved_path,
                size_bytes=size_bytes,
            )
        )
    return targets, skipped


def sql_uuid_array(values: set[str]) -> list[str]:
    """将 UUID 集合转换为 PostgreSQL 数组参数。"""
    return sorted(values)


def sql_bigint_array(values: set[int]) -> list[int]:
    """将 bigint 集合转换为 PostgreSQL 数组参数。"""
    return sorted(values)


def count_database_targets(connection, selection: CleanupSelection) -> dict[str, int]:
    """统计 dry-run 和执行摘要中的 PostgreSQL 清理规模。"""
    user_ids = sql_bigint_array(selection.cleanup_user_ids)
    kb_ids = sql_uuid_array(selection.cleanup_knowledge_base_ids)
    file_ids = sql_uuid_array(selection.cleanup_file_ids)
    conversation_ids = sql_uuid_array(selection.cleanup_conversation_ids)

    counts = {
        "users": len(user_ids),
        "knowledge_bases": len(kb_ids),
        "knowledge_files": len(file_ids),
        "conversations": len(conversation_ids),
    }
    counts["messages"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM messages
        WHERE conversation_id = ANY(%s::uuid[]);
        """,
        (conversation_ids,),
    )
    counts["message_feedback"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM message_feedback AS mf
        WHERE mf.user_id = ANY(%s::bigint[])
           OR mf.message_id IN (
                SELECT id
                FROM messages
                WHERE conversation_id = ANY(%s::uuid[])
           );
        """,
        (user_ids, conversation_ids),
    )
    counts["message_source_feedback"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM message_source_feedback AS msf
        WHERE msf.user_id = ANY(%s::bigint[])
           OR msf.knowledge_file_id = ANY(%s::uuid[])
           OR msf.message_id IN (
                SELECT id
                FROM messages
                WHERE conversation_id = ANY(%s::uuid[])
           );
        """,
        (user_ids, file_ids, conversation_ids),
    )
    counts["knowledge_base_files"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM knowledge_base_files
        WHERE knowledge_base_id = ANY(%s::uuid[])
           OR knowledge_file_id = ANY(%s::uuid[]);
        """,
        (kb_ids, file_ids),
    )
    counts["knowledge_file_chunks"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM knowledge_file_chunks
        WHERE user_id = ANY(%s::bigint[])
           OR knowledge_file_id = ANY(%s::uuid[]);
        """,
        (user_ids, file_ids),
    )
    counts["vector_index_jobs"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM vector_index_jobs
        WHERE user_id = ANY(%s::bigint[])
           OR knowledge_base_id = ANY(%s::uuid[])
           OR knowledge_file_id = ANY(%s::uuid[]);
        """,
        (user_ids, kb_ids, file_ids),
    )
    counts["knowledge_base_retrieval_settings"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM knowledge_base_retrieval_settings
        WHERE user_id = ANY(%s::bigint[])
           OR knowledge_base_id = ANY(%s::uuid[]);
        """,
        (user_ids, kb_ids),
    )
    counts["user_llm_settings"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM user_llm_settings
        WHERE user_id = ANY(%s::bigint[]);
        """,
        (user_ids,),
    )
    counts["user_llm_provider_credentials"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM user_llm_provider_credentials
        WHERE user_id = ANY(%s::bigint[]);
        """,
        (user_ids,),
    )
    counts["user_embedding_settings"] = fetch_count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM user_embedding_settings
        WHERE user_id = ANY(%s::bigint[]);
        """,
        (user_ids,),
    )
    return counts


def normalize_collection_name_part(value: str) -> str:
    """将 collection 名称片段规范化为 Chroma 可接受的安全字符。"""
    normalized = "".join(
        character if character.isalnum() or character in {"_", "-"} else "-"
        for character in value.strip().lower()
    ).strip("-_")
    return normalized or "collection"


def is_demo_collection_name(collection_name: str, base_collection_name: str) -> bool:
    """判断 collection 是否属于 FirstRAG 的默认或用户隔离集合。"""
    normalized_base = normalize_collection_name_part(base_collection_name)[:24]
    return (
        collection_name == base_collection_name
        or collection_name == normalized_base
        or collection_name.startswith(f"{normalized_base}-u")
    )


def build_chroma_filter(user_id: int, file_id: str) -> dict[str, Any]:
    """构造按用户和文件清理 Chroma entries 的 metadata filter。"""
    return {
        "$and": [
            {"user_id": str(user_id)},
            {"file_id": file_id},
        ]
    }


def cleanup_chroma_entries(
    files: Sequence[Row],
    vector_store_path: Path,
    collection_name: str,
    *,
    execute: bool,
    skip_chroma: bool,
) -> tuple[list[VectorCleanupResult], list[str]]:
    """统计或删除 Chroma 中与待清理文件对应的向量 entries。"""
    warnings: list[str] = []
    if skip_chroma:
        warnings.append("已跳过 Chroma 统计和清理。")
        return [], warnings

    if not files:
        return [], warnings

    if not vector_store_path.exists():
        warnings.append(f"Chroma 路径不存在，向量 entries 统计为 0：{vector_store_path}")
        return [], warnings

    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - 依赖缺失时才触发。
        raise DemoCleanupError(
            "缺少 chromadb 依赖，无法审计或清理 Chroma entries。"
        ) from exc

    client = chromadb.PersistentClient(path=str(vector_store_path))
    collection_refs = client.list_collections()
    collection_names = [
        getattr(collection_ref, "name", collection_ref)
        for collection_ref in collection_refs
    ]
    target_collection_names = [
        name
        for name in collection_names
        if isinstance(name, str) and is_demo_collection_name(name, collection_name)
    ]

    results: list[VectorCleanupResult] = []
    for target_collection_name in target_collection_names:
        collection = client.get_collection(target_collection_name)
        for file_row in files:
            file_id = normalize_uuid(file_row["id"])
            user_id = int(file_row["user_id"])
            where = build_chroma_filter(user_id, file_id)
            matched = collection.get(where=where, include=[])
            matched_ids = list(matched.get("ids", []))
            deleted_count = 0
            if execute and matched_ids:
                collection.delete(ids=matched_ids)
                deleted_count = len(matched_ids)
            results.append(
                VectorCleanupResult(
                    collection_name=target_collection_name,
                    file_id=file_id,
                    user_id=user_id,
                    matched_count=len(matched_ids),
                    deleted_count=deleted_count,
                )
            )
    return results, warnings


def build_cleanup_plan(
    connection,
    snapshot: DatabaseSnapshot,
    retention: RetentionConfig,
    uploads_dir: Path,
    vector_store_path: Path,
    collection_name: str,
    *,
    skip_chroma: bool,
) -> CleanupPlan:
    """构建完整清理计划，并统计 Chroma 与 uploads 影响面。"""
    selection = build_cleanup_selection(snapshot, retention)
    candidate_files = list_candidate_files(snapshot, selection.cleanup_file_ids)
    upload_targets, skipped_upload_targets = build_upload_targets(
        candidate_files,
        uploads_dir,
    )
    counts = count_database_targets(connection, selection)
    counts["upload_files"] = len(upload_targets)
    counts["upload_bytes"] = sum(target.size_bytes for target in upload_targets)

    vector_results, warnings = cleanup_chroma_entries(
        candidate_files,
        vector_store_path,
        collection_name,
        execute=False,
        skip_chroma=skip_chroma,
    )
    counts["chroma_entries"] = sum(result.matched_count for result in vector_results)
    counts["chroma_deleted_entries"] = sum(
        result.deleted_count
        for result in vector_results
    )

    return CleanupPlan(
        cutoff=retention.cutoff,
        selection=selection,
        counts=counts,
        upload_targets=upload_targets,
        skipped_upload_targets=skipped_upload_targets,
        vector_results=vector_results,
        warnings=warnings,
    )


def delete_database_targets(connection, selection: CleanupSelection) -> dict[str, int]:
    """按安全顺序删除 PostgreSQL 中的 demo 数据。"""
    user_ids = sql_bigint_array(selection.cleanup_user_ids)
    kb_ids = sql_uuid_array(selection.cleanup_knowledge_base_ids)
    file_ids = sql_uuid_array(selection.cleanup_file_ids)
    conversation_ids = sql_uuid_array(selection.cleanup_conversation_ids)
    deleted: dict[str, int] = {}

    statements: list[tuple[str, str, tuple[Any, ...]]] = [
        (
            "message_source_feedback",
            """
            DELETE FROM message_source_feedback AS msf
            WHERE msf.user_id = ANY(%s::bigint[])
               OR msf.knowledge_file_id = ANY(%s::uuid[])
               OR msf.message_id IN (
                    SELECT id
                    FROM messages
                    WHERE conversation_id = ANY(%s::uuid[])
               );
            """,
            (user_ids, file_ids, conversation_ids),
        ),
        (
            "message_feedback",
            """
            DELETE FROM message_feedback AS mf
            WHERE mf.user_id = ANY(%s::bigint[])
               OR mf.message_id IN (
                    SELECT id
                    FROM messages
                    WHERE conversation_id = ANY(%s::uuid[])
               );
            """,
            (user_ids, conversation_ids),
        ),
        (
            "messages",
            """
            DELETE FROM messages
            WHERE conversation_id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        ),
        (
            "conversations",
            """
            DELETE FROM conversations
            WHERE id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        ),
        (
            "knowledge_base_retrieval_settings",
            """
            DELETE FROM knowledge_base_retrieval_settings
            WHERE user_id = ANY(%s::bigint[])
               OR knowledge_base_id = ANY(%s::uuid[]);
            """,
            (user_ids, kb_ids),
        ),
        (
            "vector_index_jobs",
            """
            DELETE FROM vector_index_jobs
            WHERE user_id = ANY(%s::bigint[])
               OR knowledge_base_id = ANY(%s::uuid[])
               OR knowledge_file_id = ANY(%s::uuid[]);
            """,
            (user_ids, kb_ids, file_ids),
        ),
        (
            "knowledge_file_chunks",
            """
            DELETE FROM knowledge_file_chunks
            WHERE user_id = ANY(%s::bigint[])
               OR knowledge_file_id = ANY(%s::uuid[]);
            """,
            (user_ids, file_ids),
        ),
        (
            "knowledge_base_files",
            """
            DELETE FROM knowledge_base_files
            WHERE knowledge_base_id = ANY(%s::uuid[])
               OR knowledge_file_id = ANY(%s::uuid[]);
            """,
            (kb_ids, file_ids),
        ),
        (
            "knowledge_files",
            """
            DELETE FROM knowledge_files
            WHERE id = ANY(%s::uuid[]);
            """,
            (file_ids,),
        ),
        (
            "knowledge_bases",
            """
            DELETE FROM knowledge_bases
            WHERE id = ANY(%s::uuid[]);
            """,
            (kb_ids,),
        ),
        (
            "user_llm_settings",
            """
            DELETE FROM user_llm_settings
            WHERE user_id = ANY(%s::bigint[]);
            """,
            (user_ids,),
        ),
        (
            "user_llm_provider_credentials",
            """
            DELETE FROM user_llm_provider_credentials
            WHERE user_id = ANY(%s::bigint[]);
            """,
            (user_ids,),
        ),
        (
            "user_embedding_settings",
            """
            DELETE FROM user_embedding_settings
            WHERE user_id = ANY(%s::bigint[]);
            """,
            (user_ids,),
        ),
        (
            "users",
            """
            DELETE FROM users
            WHERE id = ANY(%s::bigint[]);
            """,
            (user_ids,),
        ),
    ]

    with connection.transaction():
        with connection.cursor() as cursor:
            for name, sql, params in statements:
                cursor.execute(sql, params)
                deleted[name] = cursor.rowcount
    return deleted


def summarize_path(path: Path, uploads_dir: Path) -> str:
    """输出不含文件内容的安全路径摘要。"""
    uploads_root = uploads_dir.resolve()
    try:
        return str(path.resolve().relative_to(uploads_root))
    except ValueError:
        return path.name


def prune_empty_parents(path: Path, uploads_dir: Path) -> None:
    """删除上传文件后向上清理空目录，但不越过 uploads 根目录。"""
    uploads_root = uploads_dir.resolve()
    current = path.parent.resolve()
    while current != uploads_root and is_relative_to(current, uploads_root):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent.resolve()


def delete_upload_targets(
    upload_targets: Sequence[UploadCleanupTarget],
    uploads_dir: Path,
) -> tuple[int, list[str]]:
    """删除已通过边界检查的上传文件。"""
    deleted_count = 0
    errors: list[str] = []
    for target in upload_targets:
        path = target.resolved_path
        if not path.exists():
            continue
        if not path.is_file():
            errors.append(
                f"{target.file_id}: 目标不是普通文件 {summarize_path(path, uploads_dir)}"
            )
            continue
        try:
            path.unlink()
            prune_empty_parents(path, uploads_dir)
            deleted_count += 1
        except OSError as exc:
            errors.append(
                f"{target.file_id}: 删除失败 {summarize_path(path, uploads_dir)} ({exc})"
            )
    return deleted_count, errors


def format_id_list(values: set[int] | set[str], limit: int = 12) -> str:
    """格式化 ID 列表，避免输出过长。"""
    sorted_values = sorted(str(value) for value in values)
    if len(sorted_values) <= limit:
        return ", ".join(sorted_values) or "-"
    head = ", ".join(sorted_values[:limit])
    return f"{head}, ... (+{len(sorted_values) - limit})"


def print_plan(plan: CleanupPlan, uploads_dir: Path, *, execute: bool) -> None:
    """输出清理计划或执行摘要。"""
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"FirstRAG demo cleanup plan ({mode})")
    print(f"Cutoff: {plan.cutoff.isoformat()}")
    print("Retained:")
    print(f"  users: {format_id_list(plan.selection.retained_user_ids)}")
    print(
        "  knowledge_bases: "
        f"{format_id_list(plan.selection.retained_knowledge_base_ids)}"
    )
    print(f"  files: {format_id_list(plan.selection.retained_file_ids)}")
    print("Candidates:")
    print(
        "  users: "
        f"{plan.counts['users']} ids=[{format_id_list(plan.selection.cleanup_user_ids)}]"
    )
    print(
        "  knowledge_bases: "
        f"{plan.counts['knowledge_bases']} "
        f"ids=[{format_id_list(plan.selection.cleanup_knowledge_base_ids)}]"
    )
    print(
        "  files: "
        f"{plan.counts['knowledge_files']} "
        f"ids=[{format_id_list(plan.selection.cleanup_file_ids)}]"
    )
    print(
        "  conversations: "
        f"{plan.counts['conversations']} "
        f"ids=[{format_id_list(plan.selection.cleanup_conversation_ids)}]"
    )
    print("PostgreSQL rows:")
    for key in sorted(plan.counts):
        if key in {
            "users",
            "knowledge_bases",
            "knowledge_files",
            "conversations",
            "upload_files",
            "upload_bytes",
            "chroma_entries",
            "chroma_deleted_entries",
        }:
            continue
        print(f"  {key}: {plan.counts[key]}")
    print("Chroma:")
    print(f"  matched_entries: {plan.counts['chroma_entries']}")
    collections: dict[str, int] = defaultdict(int)
    for result in plan.vector_results:
        collections[result.collection_name] += result.matched_count
    for collection_name, matched_count in sorted(collections.items()):
        print(f"  collection {collection_name}: {matched_count}")
    print("Uploads:")
    print(
        f"  files: {plan.counts['upload_files']} "
        f"bytes={plan.counts['upload_bytes']}"
    )
    for target in plan.upload_targets[:12]:
        print(
            "  path: "
            f"{target.file_id} {summarize_path(target.resolved_path, uploads_dir)}"
        )
    if len(plan.upload_targets) > 12:
        print(f"  ... (+{len(plan.upload_targets) - 12} paths)")
    if plan.skipped_upload_targets:
        print("Skipped upload paths:")
        for target in plan.skipped_upload_targets:
            print(f"  {target.file_id}: {target.reason}")
    if plan.warnings:
        print("Warnings:")
        for warning in plan.warnings:
            print(f"  {warning}")
    if not execute:
        print(
            "Dry run only. Re-run with "
            f"--execute --confirm {DEFAULT_CONFIRM_TEXT} to apply."
        )


def execute_cleanup(
    connection,
    plan: CleanupPlan,
    uploads_dir: Path,
    vector_store_path: Path,
    collection_name: str,
    candidate_files: Sequence[Row],
    *,
    skip_chroma: bool,
) -> tuple[dict[str, int], int, list[str], int, list[str]]:
    """执行 PostgreSQL 和 uploads 清理。"""
    if plan.skipped_upload_targets:
        raise DemoCleanupError(
            "存在越界或不可解析的上传路径，已停止执行；请先修正 storage_path 或保留这些文件。"
        )

    vector_results, vector_warnings = cleanup_chroma_entries(
        candidate_files,
        vector_store_path,
        collection_name,
        execute=True,
        skip_chroma=skip_chroma,
    )
    deleted_rows = delete_database_targets(connection, plan.selection)
    deleted_uploads, upload_errors = delete_upload_targets(
        plan.upload_targets,
        uploads_dir,
    )
    deleted_vectors = sum(result.deleted_count for result in vector_results)
    return (
        deleted_rows,
        deleted_uploads,
        upload_errors,
        deleted_vectors,
        vector_warnings,
    )


def run(args: argparse.Namespace) -> int:
    """执行命令行请求。"""
    env = build_runtime_env(args.env_file)
    database_url = load_database_url(args.database_url, env)
    uploads_dir = resolve_uploads_dir(args, env)
    vector_store_path = resolve_vector_store_path(args, env)
    collection_name = (
        args.chroma_collection_name
        or env.get("CHROMA_COLLECTION_NAME")
        or DEFAULT_CHROMA_COLLECTION_NAME
    )
    if args.older_than_days < 0:
        raise DemoCleanupError("--older-than-days 不能小于 0。")
    if args.execute and args.confirm != DEFAULT_CONFIRM_TEXT:
        raise DemoCleanupError(
            f"执行模式需要显式传入 --confirm {DEFAULT_CONFIRM_TEXT}。"
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
    with connect_database(database_url) as connection:
        snapshot = load_database_snapshot(connection)
        retain_user_ids = set(args.retain_user_id) | resolve_usernames(
            snapshot,
            args.retain_user,
            "--retain-user",
        )
        cleanup_user_ids = set(args.cleanup_user_id) | resolve_usernames(
            snapshot,
            args.cleanup_user,
            "--cleanup-user",
        )
        retention = RetentionConfig(
            retain_user_ids=retain_user_ids,
            retain_knowledge_base_ids=parse_uuid_set(
                args.retain_knowledge_base_id,
                "--retain-knowledge-base-id",
            ),
            retain_file_ids=parse_uuid_set(args.retain_file_id, "--retain-file-id"),
            cleanup_user_ids=cleanup_user_ids,
            cutoff=cutoff,
        )
        plan = build_cleanup_plan(
            connection,
            snapshot,
            retention,
            uploads_dir,
            vector_store_path,
            collection_name,
            skip_chroma=args.skip_chroma,
        )
        print_plan(plan, uploads_dir, execute=args.execute)
        if not args.execute:
            return 0

        candidate_files = list_candidate_files(
            snapshot,
            plan.selection.cleanup_file_ids,
        )
        (
            deleted_rows,
            deleted_uploads,
            upload_errors,
            deleted_vectors,
            vector_warnings,
        ) = execute_cleanup(
            connection,
            plan,
            uploads_dir,
            vector_store_path,
            collection_name,
            candidate_files,
            skip_chroma=args.skip_chroma,
        )
        print("Execution summary:")
        print(f"  chroma_deleted_entries: {deleted_vectors}")
        for name in sorted(deleted_rows):
            print(f"  {name}: {deleted_rows[name]}")
        print(f"  uploads_deleted: {deleted_uploads}")
        for warning in vector_warnings:
            print(f"  warning: {warning}")
        if upload_errors:
            print("Upload deletion errors:")
            for error in upload_errors:
                print(f"  {error}")
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except DemoCleanupError as exc:
        print(f"Demo cleanup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
