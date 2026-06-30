from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import migrate_db


class FakeTransaction:
    """测试用事务上下文。"""

    def __init__(self, connection: "FakeConnection") -> None:
        """保存 fake connection。"""
        self.connection = connection

    def __enter__(self) -> "FakeTransaction":
        """进入事务。"""
        self.connection.transaction_depth += 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """离开事务。"""
        self.connection.transaction_depth -= 1


class FakeCursor:
    """测试用 cursor。"""

    def __init__(self, connection: "FakeConnection") -> None:
        """保存 fake connection。"""
        self.connection = connection
        self._fetchone = None
        self._fetchall = []

    def __enter__(self) -> "FakeCursor":
        """进入 cursor 上下文。"""
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """离开 cursor 上下文。"""

    def execute(self, sql: str, params: tuple | None = None) -> None:
        """记录执行过的 SQL，并模拟 migration 记录表。"""
        self.connection.executed_sql.append(sql)
        if "BROKEN SQL" in sql:
            raise RuntimeError("broken migration")
        if "SELECT to_regclass" in sql:
            self._fetchone = ("schema_migrations",)
            return
        if "FROM schema_migrations" in sql:
            self._fetchall = [
                (
                    migration.filename,
                    migration.checksum,
                    migration.status,
                )
                for migration in self.connection.applied.values()
            ]
            return
        if "INSERT INTO schema_migrations" in sql and params is not None:
            filename, checksum, _execution_time_ms = params
            self.connection.applied[filename] = migrate_db.AppliedMigration(
                filename=filename,
                checksum=checksum,
                status="succeeded",
            )

    def fetchone(self):
        """返回单行查询结果。"""
        return self._fetchone

    def fetchall(self):
        """返回多行查询结果。"""
        return self._fetchall


class FakeConnection:
    """测试用 connection。"""

    def __init__(self) -> None:
        """初始化 fake connection 状态。"""
        self.applied: dict[str, migrate_db.AppliedMigration] = {}
        self.executed_sql: list[str] = []
        self.transaction_depth = 0

    def cursor(self) -> FakeCursor:
        """创建 fake cursor。"""
        return FakeCursor(self)

    def transaction(self) -> FakeTransaction:
        """创建 fake transaction。"""
        return FakeTransaction(self)


class MigrateDbScriptTests(unittest.TestCase):
    """数据库迁移脚本测试。"""

    def test_discover_migrations_orders_files_and_hashes_content(self) -> None:
        """读取 migration 时应按文件名排序并计算 checksum。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            sql_dir = Path(tmpdir)
            second = sql_dir / "002_second.sql"
            first = sql_dir / "001_first.sql"
            second.write_text("SELECT 2;\n", encoding="utf-8")
            first.write_text("SELECT 1;\n", encoding="utf-8")
            (sql_dir / "README.md").write_text("ignored\n", encoding="utf-8")
            expected_second_checksum = migrate_db.calculate_checksum(second)

            migrations = migrate_db.discover_migrations(sql_dir)

        self.assertEqual(
            [migration.filename for migration in migrations],
            ["001_first.sql", "002_second.sql"],
        )
        self.assertEqual(migrations[0].sql, "SELECT 1;\n")
        self.assertEqual(migrations[1].checksum, expected_second_checksum)

    def test_plan_migrations_skips_applied_and_marks_pending(self) -> None:
        """已应用且 checksum 一致的 migration 应跳过，未应用的应 pending。"""
        first = migrate_db.Migration(
            filename="000_initial_schema.sql",
            path=Path("000_initial_schema.sql"),
            checksum="abc",
            sql="SELECT 1;",
        )
        second = migrate_db.Migration(
            filename="001_add_table.sql",
            path=Path("001_add_table.sql"),
            checksum="def",
            sql="SELECT 2;",
        )

        plan = migrate_db.plan_migrations(
            [first, second],
            {
                first.filename: migrate_db.AppliedMigration(
                    filename=first.filename,
                    checksum=first.checksum,
                    status="succeeded",
                )
            },
        )

        self.assertEqual([item.action for item in plan], ["skipped", "pending"])

    def test_plan_migrations_rejects_checksum_mismatch(self) -> None:
        """已执行 migration 的 checksum 变化时应停止。"""
        migration = migrate_db.Migration(
            filename="000_initial_schema.sql",
            path=Path("000_initial_schema.sql"),
            checksum="new",
            sql="SELECT 1;",
        )

        with self.assertRaisesRegex(migrate_db.MigrationError, "checksum"):
            migrate_db.plan_migrations(
                [migration],
                {
                    migration.filename: migrate_db.AppliedMigration(
                        filename=migration.filename,
                        checksum="old",
                        status="succeeded",
                    )
                },
            )

    def test_apply_pending_migrations_stops_after_failure(self) -> None:
        """某个 migration 失败时不应继续执行后续 migration。"""
        connection = FakeConnection()
        migrations = [
            migrate_db.Migration(
                filename="001_ok.sql",
                path=Path("001_ok.sql"),
                checksum="ok",
                sql="SELECT 1;",
            ),
            migrate_db.Migration(
                filename="002_broken.sql",
                path=Path("002_broken.sql"),
                checksum="broken",
                sql="BROKEN SQL",
            ),
            migrate_db.Migration(
                filename="003_later.sql",
                path=Path("003_later.sql"),
                checksum="later",
                sql="SELECT 3;",
            ),
        ]
        plan = [
            migrate_db.MigrationPlanItem(migration=migration, action="pending")
            for migration in migrations
        ]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(migrate_db.MigrationError, "002_broken"):
                migrate_db.apply_pending_migrations(connection, plan)

        self.assertIn("001_ok.sql", connection.applied)
        self.assertNotIn("002_broken.sql", connection.applied)
        self.assertNotIn("003_later.sql", connection.applied)
        self.assertFalse(
            any("SELECT 3;" in sql for sql in connection.executed_sql),
        )


if __name__ == "__main__":
    unittest.main()
