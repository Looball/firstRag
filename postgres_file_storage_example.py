"""
FastAPI + PostgreSQL file storage example.

Required packages:
    pip install "psycopg[binary]" fastapi uvicorn

Required environment variable:
    export DATABASE_URL="postgresql://user:password@localhost:5432/first_rag"

Run:
    python postgres_file_storage_example.py

Example requests:
    curl -F "file=@./local_doc/example.pdf" http://127.0.0.1:8000/files
    curl http://127.0.0.1:8000/files
    curl -OJ http://127.0.0.1:8000/files/1/download
"""

from __future__ import annotations

import hashlib
import os
from typing import Any
from urllib.parse import quote

import psycopg
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from psycopg.rows import dict_row


DATABASE_URL = os.environ.get("DATABASE_URL")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

app = FastAPI(title="PostgreSQL File Storage Example")


def get_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "Missing DATABASE_URL, for example: "
            "postgresql://user:password@localhost:5432/first_rag"
        )
    return DATABASE_URL


def get_connection() -> psycopg.Connection[Any]:
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def init_db() -> None:
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS stored_files (
        id BIGSERIAL PRIMARY KEY,
        filename TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
        size_bytes BIGINT NOT NULL,
        sha256 TEXT NOT NULL,
        content BYTEA NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_stored_files_created_at
        ON stored_files (created_at DESC);
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)


@app.on_event("startup")
def startup() -> None:
    init_db()


async def read_upload_file(file: UploadFile) -> tuple[bytes, int, str]:
    file_bytes = bytearray()
    sha256 = hashlib.sha256()

    while chunk := await file.read(CHUNK_SIZE):
        file_bytes.extend(chunk)
        sha256.update(chunk)

        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File is larger than MAX_FILE_SIZE_MB={MAX_FILE_SIZE // 1024 // 1024}",
            )

    return bytes(file_bytes), len(file_bytes), sha256.hexdigest()


@app.post("/files")
async def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    content, size_bytes, digest = await read_upload_file(file)

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Empty files are not supported")

    insert_sql = """
    INSERT INTO stored_files (filename, content_type, size_bytes, sha256, content)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id, filename, content_type, size_bytes, sha256, created_at;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                insert_sql,
                (
                    file.filename or "unnamed",
                    file.content_type or "application/octet-stream",
                    size_bytes,
                    digest,
                    content,
                ),
            )
            row = cur.fetchone()

    return dict(row)


@app.get("/files")
def list_files() -> list[dict[str, Any]]:
    select_sql = """
    SELECT id, filename, content_type, size_bytes, sha256, created_at
    FROM stored_files
    ORDER BY created_at DESC, id DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(select_sql)
            return [dict(row) for row in cur.fetchall()]


@app.get("/files/{file_id}/download")
def download_file(file_id: int) -> Response:
    select_sql = """
    SELECT filename, content_type, content
    FROM stored_files
    WHERE id = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(select_sql, (file_id,))
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="File not found")

    filename = row["filename"]
    content_type = row["content_type"] or "application/octet-stream"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
    }

    return Response(
        content=bytes(row["content"]),
        media_type=content_type,
        headers=headers,
    )


@app.delete("/files/{file_id}")
def delete_file(file_id: int) -> dict[str, Any]:
    delete_sql = """
    DELETE FROM stored_files
    WHERE id = %s
    RETURNING id, filename;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(delete_sql, (file_id,))
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {"deleted": True, "file": dict(row)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("postgres_file_storage_example:app", host="127.0.0.1", port=8000, reload=True)
