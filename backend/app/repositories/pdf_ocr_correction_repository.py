"""扫描 PDF 页级人工 OCR 修订数据访问。"""

from uuid import UUID

from app.db.executor import Row, execute, fetch_all, fetch_one


def get_pdf_ocr_correction(
    user_id: int,
    knowledge_file_id: UUID | str,
    page_number: int,
) -> Row | None:
    """读取当前用户指定文件页的人工修订。"""
    return fetch_one(
        """
        SELECT
            user_id,
            knowledge_file_id,
            page_number,
            original_ocr_text,
            corrected_text,
            revision,
            created_at,
            updated_at
        FROM knowledge_file_ocr_corrections
        WHERE user_id = %s
          AND knowledge_file_id = %s
          AND page_number = %s;
        """,
        (user_id, str(knowledge_file_id), page_number),
    )


def list_pdf_ocr_corrections(
    user_id: int,
    knowledge_file_id: UUID | str,
) -> list[Row]:
    """读取单个文件全部有效页级人工修订。"""
    return fetch_all(
        """
        SELECT
            page_number,
            corrected_text,
            revision,
            updated_at
        FROM knowledge_file_ocr_corrections
        WHERE user_id = %s
          AND knowledge_file_id = %s
        ORDER BY page_number ASC;
        """,
        (user_id, str(knowledge_file_id)),
    )


def upsert_pdf_ocr_correction(
    user_id: int,
    knowledge_file_id: UUID | str,
    page_number: int,
    original_ocr_text: str,
    corrected_text: str,
) -> Row:
    """新增或更新页级人工修订，并递增修订版本。"""
    row = fetch_one(
        """
        INSERT INTO knowledge_file_ocr_corrections (
            user_id,
            knowledge_file_id,
            page_number,
            original_ocr_text,
            corrected_text
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id, knowledge_file_id, page_number)
        DO UPDATE SET
            corrected_text = EXCLUDED.corrected_text,
            revision = knowledge_file_ocr_corrections.revision + 1,
            updated_at = now()
        RETURNING
            user_id,
            knowledge_file_id,
            page_number,
            original_ocr_text,
            corrected_text,
            revision,
            created_at,
            updated_at;
        """,
        (
            user_id,
            str(knowledge_file_id),
            page_number,
            original_ocr_text,
            corrected_text,
        ),
    )
    if row is None:
        raise RuntimeError("OCR 人工修订保存失败")
    return row


def delete_pdf_ocr_correction(
    user_id: int,
    knowledge_file_id: UUID | str,
    page_number: int,
) -> int:
    """删除当前用户指定页面的人工修订。"""
    return execute(
        """
        DELETE FROM knowledge_file_ocr_corrections
        WHERE user_id = %s
          AND knowledge_file_id = %s
          AND page_number = %s;
        """,
        (user_id, str(knowledge_file_id), page_number),
    )
