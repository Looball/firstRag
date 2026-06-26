from collections.abc import Sequence
from typing import Any

from app.db.connection import get_connection


type QueryParams = Sequence[Any]
type Row = dict[str, Any]


def fetch_all(
    sql: str,
    params: QueryParams = (),
) -> list[Row]:
    """执行SQL并返回全部结果行。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())


def fetch_one(
    sql: str,
    params: QueryParams = (),
) -> Row | None:
    """执行SQL并返回第一行，没有结果时返回None。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None


def execute(
    sql: str,
    params: QueryParams = (),
) -> int:
    """执行不需要返回结果集的SQL并返回受影响行数。"""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount
