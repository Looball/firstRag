import os

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


def get_connection() -> Connection:
    """创建使用字典行格式的PostgreSQL连接。"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("缺少环境变量 DATABASE_URL")

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
    )
