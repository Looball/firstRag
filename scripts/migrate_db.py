#!/usr/bin/env python3
"""FirstRAG 数据库迁移执行入口。"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQL_DIR = PROJECT_ROOT / "backend/app/db/sql"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
MIGRATION_FILENAME_WIDTH = 3


class MigrationError(RuntimeError):
    """数据库迁移失败。"""


@dataclass(frozen=True)
class Migration:
    """单个 migration SQL 文件。"""

    filename: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class AppliedMigration:
    """数据库中已记录的 migration。"""

    filename: str
    checksum: str
    status: str


MigrationAction = Literal["pending", "skipped"]


@dataclass(frozen=True)
class MigrationPlanItem:
    """待执行计划中的单个 migration 项。"""

    migration: Migration
    action: MigrationAction


def build_arg_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Apply FirstRAG database migrations.",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL, then COMPOSE_DATABASE_URL.",
    )
    parser.add_argument(
        "--sql-dir",
        type=Path,
        default=DEFAULT_SQL_DIR,
        help="Directory containing numbered SQL migrations.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Dotenv file to load before reading DATABASE_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying them.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List local migration files and checksums without connecting.",
    )
    return parser


def calculate_checksum(path: Path) -> str:
    """计算 SQL 文件的 SHA-256 checksum。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_migration_filename(path: Path) -> None:
    """校验 migration 文件名是否符合三位编号约定。"""
    prefix = path.name.split("_", 1)[0]
    if (
        len(prefix) != MIGRATION_FILENAME_WIDTH
        or not prefix.isdigit()
        or "_" not in path.name
    ):
        raise MigrationError(
            f"migration 文件名必须使用三位编号和英文描述：{path.name}"
        )


def discover_migrations(sql_dir: Path) -> list[Migration]:
    """读取并按文件名排序 migration SQL。"""
    if not sql_dir.exists():
        raise MigrationError(f"migration 目录不存在：{sql_dir}")
    if not sql_dir.is_dir():
        raise MigrationError(f"migration 路径不是目录：{sql_dir}")

    paths = sorted(sql_dir.glob("*.sql"))
    if not paths:
        raise MigrationError(f"migration 目录中没有 SQL 文件：{sql_dir}")

    seen_versions: set[str] = set()
    migrations: list[Migration] = []
    for path in paths:
        validate_migration_filename(path)
        version = path.name.split("_", 1)[0]
        if version in seen_versions:
            raise MigrationError(f"migration 编号重复：{version}")
        seen_versions.add(version)
        migrations.append(
            Migration(
                filename=path.name,
                path=path,
                checksum=calculate_checksum(path),
                sql=path.read_text(encoding="utf-8"),
            )
        )
    return migrations


def load_database_url(
    explicit_database_url: str | None,
    env_file: Path,
) -> str:
    """读取数据库连接串，不向 stdout/stderr 输出敏感内容。"""
    if explicit_database_url:
        return explicit_database_url

    if env_file.exists():
        load_env_file(env_file)

    database_url = os.environ.get("DATABASE_URL") or os.environ.get(
        "COMPOSE_DATABASE_URL"
    )
    if not database_url:
        raise MigrationError(
            "缺少数据库连接配置，请设置 DATABASE_URL 或传入 --database-url。"
        )
    return database_url


def load_env_file(env_file: Path) -> None:
    """加载 .env；缺少 python-dotenv 时只读取简单 KEY=VALUE 行。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_simple_env_file(env_file)
        return

    load_dotenv(env_file, override=False)


def load_simple_env_file(env_file: Path) -> None:
    """在无 python-dotenv 环境下读取简单 dotenv 配置。"""
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("'\"")


def connect_database(database_url: str):
    """创建 PostgreSQL 连接。"""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - 依赖缺失时才触发。
        raise MigrationError(
            "缺少 psycopg 依赖，请先安装 backend/requirements.txt。"
        ) from exc

    try:
        connection = psycopg.connect(database_url)
        connection.autocommit = True
        return connection
    except Exception as exc:  # pragma: no cover - 真实连接错误由集成环境覆盖。
        raise MigrationError(
            "连接数据库失败，请检查 DATABASE_URL 和数据库服务状态。"
        ) from exc


def ensure_schema_migrations_table(connection) -> None:
    """创建 migration 记录表。"""
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'succeeded',
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    execution_time_ms INTEGER NOT NULL DEFAULT 0,
                    CONSTRAINT schema_migrations_status_check
                        CHECK (status IN ('succeeded'))
                );
                """
            )


def schema_migrations_table_exists(connection) -> bool:
    """检查 migration 记录表是否已经存在。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.schema_migrations');")
        row = cursor.fetchone()
    return bool(row and row[0])


def read_applied_migrations(connection) -> dict[str, AppliedMigration]:
    """读取数据库中已成功应用的 migrations。"""
    if not schema_migrations_table_exists(connection):
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT filename, checksum, status
            FROM schema_migrations
            ORDER BY filename;
            """
        )
        rows = cursor.fetchall()

    applied: dict[str, AppliedMigration] = {}
    for row in rows:
        filename, checksum, status = row
        applied[filename] = AppliedMigration(
            filename=filename,
            checksum=checksum,
            status=status,
        )
    return applied


def plan_migrations(
    migrations: list[Migration],
    applied: dict[str, AppliedMigration],
) -> list[MigrationPlanItem]:
    """根据已执行记录生成迁移计划，并校验 checksum。"""
    plan: list[MigrationPlanItem] = []
    for migration in migrations:
        applied_migration = applied.get(migration.filename)
        if applied_migration is None:
            plan.append(MigrationPlanItem(migration=migration, action="pending"))
            continue

        if applied_migration.checksum != migration.checksum:
            raise MigrationError(
                "migration checksum 不一致，已停止执行："
                f"{migration.filename}"
            )

        if applied_migration.status != "succeeded":
            raise MigrationError(
                "migration 记录状态异常，已停止执行："
                f"{migration.filename} ({applied_migration.status})"
            )

        plan.append(MigrationPlanItem(migration=migration, action="skipped"))
    return plan


def apply_migration(connection, migration: Migration) -> int:
    """在单独事务中执行一个 migration，并记录 checksum。"""
    started_at = time.perf_counter()
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(migration.sql)
            execution_time_ms = int((time.perf_counter() - started_at) * 1000)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO schema_migrations (
                        filename,
                        checksum,
                        status,
                        execution_time_ms
                    )
                    VALUES (%s, %s, 'succeeded', %s);
                    """,
                    (
                        migration.filename,
                        migration.checksum,
                        execution_time_ms,
                    ),
                )
    except Exception as exc:
        raise MigrationError(
            f"migration 执行失败，已停止后续文件：{migration.filename}"
        ) from exc
    return execution_time_ms


def apply_pending_migrations(
    connection,
    plan: list[MigrationPlanItem],
) -> tuple[int, int]:
    """执行计划中的 pending migrations，返回 applied/skipped 数量。"""
    applied_count = 0
    skipped_count = 0
    for item in plan:
        if item.action == "skipped":
            skipped_count += 1
            print(f"Skipped {item.migration.filename} (already applied)")
            continue

        execution_time_ms = apply_migration(connection, item.migration)
        applied_count += 1
        print(f"Applied {item.migration.filename} in {execution_time_ms}ms")
    return applied_count, skipped_count


def print_local_migrations(migrations: list[Migration]) -> None:
    """输出本地 migration 文件列表。"""
    for migration in migrations:
        print(f"{migration.filename} {migration.checksum}")


def print_plan(plan: list[MigrationPlanItem]) -> None:
    """输出迁移计划。"""
    for item in plan:
        print(f"{item.action.upper():7} {item.migration.filename}")


def run(args: argparse.Namespace) -> int:
    """执行命令行请求。"""
    migrations = discover_migrations(args.sql_dir)

    if args.list:
        print_local_migrations(migrations)
        return 0

    database_url = load_database_url(args.database_url, args.env_file)
    with connect_database(database_url) as connection:
        if not args.dry_run:
            ensure_schema_migrations_table(connection)

        applied = read_applied_migrations(connection)
        plan = plan_migrations(migrations, applied)

        if args.dry_run:
            print_plan(plan)
            pending_count = sum(1 for item in plan if item.action == "pending")
            skipped_count = len(plan) - pending_count
            print(
                "Dry run complete: "
                f"pending={pending_count} skipped={skipped_count}"
            )
            return 0

        applied_count, skipped_count = apply_pending_migrations(
            connection,
            plan,
        )
        print(
            "Database migrations complete: "
            f"applied={applied_count} skipped={skipped_count}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except MigrationError as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
