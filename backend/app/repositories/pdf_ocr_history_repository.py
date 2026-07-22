"""PDF 页级 OCR 原始识别历史数据访问。"""

from typing import Any
from uuid import UUID, uuid4

from app.db.connection import get_connection
from app.db.executor import Row, fetch_all


def record_pdf_ocr_history_entries(
    user_id: int,
    knowledge_file_id: UUID | str,
    entries: list[dict[str, Any]],
    max_runs_per_page: int,
) -> int:
    """写入不可变页级识别记录，并裁剪每页超出上限的旧记录。"""
    if not entries:
        return 0

    normalized_file_id = str(knowledge_file_id)
    rows = [
        (
            uuid4(),
            user_id,
            normalized_file_id,
            entry["page_number"],
            entry["index_version"],
            entry["ocr_attempt"],
            entry.get("source_job_id"),
            entry["trigger"],
            entry["ocr_engine"],
            entry.get("ocr_confidence"),
            entry["ocr_quality"],
            entry["ocr_word_count"],
            entry["ocr_text"],
            entry["ocr_text_sha256"],
            entry["ocr_text_source"],
            entry.get("correction_revision"),
        )
        for entry in entries
    ]
    page_numbers = sorted({int(entry["page_number"]) for entry in entries})
    retention_limit = max(1, max_runs_per_page)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO knowledge_file_ocr_history (
                    id,
                    user_id,
                    knowledge_file_id,
                    page_number,
                    index_version,
                    ocr_attempt,
                    source_job_id,
                    trigger,
                    ocr_engine,
                    ocr_confidence,
                    ocr_quality,
                    ocr_word_count,
                    ocr_text,
                    ocr_text_sha256,
                    ocr_text_source,
                    correction_revision
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    user_id,
                    knowledge_file_id,
                    page_number,
                    index_version
                ) DO NOTHING;
                """,
                rows,
            )
            inserted_count = max(0, cursor.rowcount)
            cursor.execute(
                """
                WITH ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY page_number
                            ORDER BY ocr_attempt DESC, created_at DESC, id DESC
                        ) AS position
                    FROM knowledge_file_ocr_history
                    WHERE user_id = %s
                      AND knowledge_file_id = %s
                      AND page_number = ANY(%s::integer[])
                )
                DELETE FROM knowledge_file_ocr_history AS history
                USING ranked
                WHERE history.id = ranked.id
                  AND ranked.position > %s;
                """,
                (
                    user_id,
                    normalized_file_id,
                    page_numbers,
                    retention_limit,
                ),
            )
            return inserted_count


def list_pdf_ocr_page_history(
    user_id: int,
    knowledge_file_id: UUID | str,
    page_number: int,
    limit: int,
) -> list[Row]:
    """按识别次数倒序读取当前用户指定页面的历史。"""
    return fetch_all(
        """
        SELECT
            history.id,
            history.page_number,
            history.index_version,
            history.ocr_attempt,
            history.source_job_id,
            history.trigger,
            history.ocr_engine,
            history.ocr_confidence,
            history.ocr_quality,
            history.ocr_word_count,
            history.ocr_text,
            history.ocr_text_sha256,
            history.ocr_text_source,
            history.correction_revision,
            history.created_at
        FROM knowledge_file_ocr_history AS history
        JOIN knowledge_files AS file
          ON file.id = history.knowledge_file_id
         AND file.user_id = history.user_id
        WHERE history.user_id = %s
          AND history.knowledge_file_id = %s
          AND history.page_number = %s
          AND file.deleted_at IS NULL
        ORDER BY history.ocr_attempt DESC, history.created_at DESC, history.id DESC
        LIMIT %s;
        """,
        (user_id, str(knowledge_file_id), page_number, max(1, limit)),
    )


def get_latest_pdf_ocr_attempts(
    user_id: int,
    knowledge_file_id: UUID | str,
) -> dict[int, int]:
    """读取文件各页最近一次持久化 OCR attempt。"""
    rows = fetch_all(
        """
        SELECT DISTINCT ON (history.page_number)
            history.page_number,
            history.ocr_attempt
        FROM knowledge_file_ocr_history AS history
        JOIN knowledge_files AS file
          ON file.id = history.knowledge_file_id
         AND file.user_id = history.user_id
        WHERE history.user_id = %s
          AND history.knowledge_file_id = %s
          AND file.deleted_at IS NULL
        ORDER BY
            history.page_number,
            history.ocr_attempt DESC,
            history.created_at DESC;
        """,
        (user_id, str(knowledge_file_id)),
    )
    return {
        int(row["page_number"]): int(row["ocr_attempt"])
        for row in rows
    }


def count_pdf_ocr_history_by_page(
    user_id: int,
    knowledge_file_id: UUID | str,
) -> dict[int, int]:
    """批量统计文件各页已保留的 OCR 历史数量。"""
    rows = fetch_all(
        """
        SELECT
            history.page_number,
            COUNT(*)::integer AS history_count
        FROM knowledge_file_ocr_history AS history
        JOIN knowledge_files AS file
          ON file.id = history.knowledge_file_id
         AND file.user_id = history.user_id
        WHERE history.user_id = %s
          AND history.knowledge_file_id = %s
          AND file.deleted_at IS NULL
        GROUP BY history.page_number;
        """,
        (user_id, str(knowledge_file_id)),
    )
    return {
        int(row["page_number"]): int(row["history_count"])
        for row in rows
    }


def get_pdf_ocr_history_summaries(
    user_id: int,
    knowledge_file_id: UUID | str,
) -> dict[int, dict[str, Any]]:
    """批量返回每页历史数量和最近两次置信度，用于巡检摘要。"""
    rows = fetch_all(
        """
        WITH ranked AS (
            SELECT
                history.page_number,
                history.ocr_confidence,
                COUNT(*) OVER (
                    PARTITION BY history.page_number
                )::integer AS history_count,
                ROW_NUMBER() OVER (
                    PARTITION BY history.page_number
                    ORDER BY
                        history.ocr_attempt DESC,
                        history.created_at DESC,
                        history.id DESC
                ) AS position
            FROM knowledge_file_ocr_history AS history
            JOIN knowledge_files AS file
              ON file.id = history.knowledge_file_id
             AND file.user_id = history.user_id
            WHERE history.user_id = %s
              AND history.knowledge_file_id = %s
              AND file.deleted_at IS NULL
        )
        SELECT
            page_number,
            MAX(history_count)::integer AS history_count,
            MAX(ocr_confidence) FILTER (WHERE position = 1)
                AS latest_confidence,
            MAX(ocr_confidence) FILTER (WHERE position = 2)
                AS previous_confidence
        FROM ranked
        WHERE position <= 2
        GROUP BY page_number;
        """,
        (user_id, str(knowledge_file_id)),
    )
    return {
        int(row["page_number"]): dict(row)
        for row in rows
    }
