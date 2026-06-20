"""PostgreSQL 咨询锁工具。"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from app.db.connection import get_connection


def build_file_index_lock_key(user_id: int, file_id: UUID | str) -> int:
    """为用户文件生成稳定的 PostgreSQL 咨询锁键。"""
    raw_key = f"vector-index:{user_id}:{file_id}".encode()
    return int.from_bytes(
        hashlib.blake2b(raw_key, digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )


@contextmanager
def file_index_lock(user_id: int, file_id: UUID | str) -> Iterator[None]:
    """在索引或删除同一文件时持有事务级咨询锁。

    Chroma 和 PostgreSQL 无法共用一个事务。该锁将同一文件的索引、删除
    操作串行化，避免旧 worker 在删除完成后再次写回向量或全文分块。
    """
    lock_key = build_file_index_lock_key(user_id, file_id)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s);", (lock_key,))
            yield
