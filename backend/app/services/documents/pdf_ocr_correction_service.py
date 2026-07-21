"""扫描 PDF 页级人工 OCR 修订与异步重建编排。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import PDF_OCR_ENABLED
from app.db.executor import Row
from app.db.locks import file_index_lock
from app.repositories.knowledge_chunk_repository import get_user_pdf_page_chunks
from app.repositories.knowledge_file_repository import (
    get_user_knowledge_file,
    reset_file_index_state,
    update_knowledge_file_status,
)
from app.repositories.pdf_ocr_correction_repository import (
    delete_pdf_ocr_correction,
    get_pdf_ocr_correction,
    upsert_pdf_ocr_correction,
)
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
)


MAX_PDF_OCR_CORRECTION_CHARACTERS = 50000
MAX_CHUNK_OVERLAP_SEARCH = 400


class PdfOcrCorrectionValidationError(ValueError):
    """文件、页码或修订正文不满足校对要求时抛出。"""


class PdfOcrCorrectionConflictError(RuntimeError):
    """文件当前状态不允许读取或修改修订时抛出。"""


def merge_overlapping_chunk_contents(rows: list[Row]) -> str:
    """按 chunk 顺序合并正文，并去除 splitter 产生的相邻重叠。"""
    contents = [str(row.get("content") or "").strip() for row in rows]
    contents = [content for content in contents if content]
    if not contents:
        return ""

    merged = contents[0]
    for content in contents[1:]:
        maximum_overlap = min(
            len(merged),
            len(content),
            MAX_CHUNK_OVERLAP_SEARCH,
        )
        overlap = next(
            (
                size
                for size in range(maximum_overlap, 0, -1)
                if merged.endswith(content[:size])
            ),
            0,
        )
        separator = "" if overlap else "\n\n"
        merged = f"{merged}{separator}{content[overlap:]}"
    return merged.strip()


def normalize_pdf_ocr_correction_text(value: str) -> str:
    """规范换行与首尾空白，并校验人工修订长度。"""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise PdfOcrCorrectionValidationError("OCR 修订文本不能为空")
    if len(normalized) > MAX_PDF_OCR_CORRECTION_CHARACTERS:
        raise PdfOcrCorrectionValidationError(
            "OCR 修订文本过长，最多允许 50000 个字符",
        )
    return normalized


def load_indexed_pdf_ocr_page(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> tuple[dict[str, Any], list[Row], dict[str, Any]] | None:
    """读取并校验当前用户已索引的 PDF OCR 页面。"""
    if page_number < 1:
        raise PdfOcrCorrectionValidationError("PDF 页码必须从 1 开始")

    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        return None
    normalized_file_record = dict(file_record)
    if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
        raise PdfOcrCorrectionValidationError("只有 PDF 文件支持 OCR 人工校对")
    if file_record["status"] != "indexed":
        raise PdfOcrCorrectionConflictError(
            "文件正在处理或尚未完成索引，请等待当前任务结束后重试",
        )

    index_version = int(file_record.get("index_version") or 0)
    page_chunks = get_user_pdf_page_chunks(
        user_id=user_id,
        file_id=knowledge_file_id,
        page_number=page_number,
        index_version=index_version,
    )
    if not page_chunks:
        raise PdfOcrCorrectionValidationError("PDF 页面不存在或尚未建立索引")
    metadata = page_chunks[0].get("metadata")
    if not isinstance(metadata, dict) or metadata.get("pdf_parse_method") != "ocr":
        raise PdfOcrCorrectionValidationError("该页面使用原生文本，不支持 OCR 校对")
    return normalized_file_record, page_chunks, metadata


def serialize_pdf_ocr_correction(
    file_record: dict[str, Any],
    page_number: int,
    page_chunks: list[Row],
    metadata: dict[str, Any],
    correction: Row | None,
) -> dict[str, Any]:
    """构造安全的 OCR 页面校对响应。"""
    reconstructed_text = merge_overlapping_chunk_contents(page_chunks)
    original_text = (
        str(correction["original_ocr_text"])
        if correction is not None
        else reconstructed_text
    )
    corrected_text = (
        str(correction["corrected_text"])
        if correction is not None
        else None
    )
    return {
        "file_id": str(file_record["id"]),
        "page_number": page_number,
        "index_version": int(file_record.get("index_version") or 0),
        "original_text": original_text,
        "current_text": corrected_text or reconstructed_text,
        "corrected_text": corrected_text,
        "has_correction": correction is not None,
        "revision": int(correction["revision"]) if correction is not None else 0,
        "updated_at": correction.get("updated_at") if correction is not None else None,
        "ocr_confidence": metadata.get("ocr_confidence"),
        "ocr_quality": metadata.get("ocr_quality") or "unknown",
    }


def get_pdf_ocr_page_correction(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> dict[str, Any] | None:
    """读取 OCR 页面正文与当前人工修订。"""
    loaded = load_indexed_pdf_ocr_page(user_id, knowledge_file_id, page_number)
    if loaded is None:
        return None
    file_record, page_chunks, metadata = loaded
    correction = get_pdf_ocr_correction(
        user_id,
        knowledge_file_id,
        page_number,
    )
    return serialize_pdf_ocr_correction(
        file_record,
        page_number,
        page_chunks,
        metadata,
        correction,
    )


def enqueue_pdf_ocr_correction_index(
    user_id: int,
    file_record: dict[str, Any],
    page_number: int,
    trigger: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """递增索引版本并提交由人工修订触发的重建任务。"""
    reset_record = reset_file_index_state(user_id, file_record["id"])
    if reset_record is None:
        raise RuntimeError("OCR 修订重建前无法更新文件索引版本")
    updated_record = {**file_record, **dict(reset_record)}
    try:
        job = enqueue_file_vector_index(
            file_record=updated_record,
            user_id=user_id,
            job_options={
                "trigger": trigger,
                "corrected_page_numbers": [page_number],
            },
        )
    except Exception:
        update_knowledge_file_status(
            user_id,
            file_record["id"],
            "failed",
            expected_index_version=reset_record["index_version"],
        )
        invalidate_file_knowledge_base_contexts(user_id, file_record["id"])
        raise
    invalidate_file_knowledge_base_contexts(user_id, file_record["id"])
    return dict(reset_record), job


def save_pdf_ocr_page_correction(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
    corrected_text: str,
) -> dict[str, Any] | None:
    """保存人工修订并提交完整文件异步重建。"""
    if not PDF_OCR_ENABLED:
        raise PdfOcrCorrectionValidationError("当前部署未启用 PDF OCR，无法保存校对")
    normalized_text = normalize_pdf_ocr_correction_text(corrected_text)

    with file_index_lock(user_id, knowledge_file_id):
        loaded = load_indexed_pdf_ocr_page(user_id, knowledge_file_id, page_number)
        if loaded is None:
            return None
        file_record, page_chunks, metadata = loaded
        existing = get_pdf_ocr_correction(user_id, knowledge_file_id, page_number)
        current_text = (
            str(existing["corrected_text"])
            if existing is not None
            else merge_overlapping_chunk_contents(page_chunks)
        )
        if normalized_text == current_text:
            raise PdfOcrCorrectionValidationError("修订文本没有变化")
        original_text = (
            str(existing["original_ocr_text"])
            if existing is not None
            else current_text
        )
        correction = upsert_pdf_ocr_correction(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_number=page_number,
            original_ocr_text=original_text,
            corrected_text=normalized_text,
        )
        previous_index_version = int(file_record.get("index_version") or 0)
        reset_record, job = enqueue_pdf_ocr_correction_index(
            user_id,
            file_record,
            page_number,
            "pdf_page_ocr_correction_saved",
        )
        response = serialize_pdf_ocr_correction(
            {**file_record, **reset_record},
            page_number,
            page_chunks,
            metadata,
            correction,
        )
        return {
            **response,
            "previous_index_version": previous_index_version,
            "job": job,
        }


def delete_pdf_ocr_page_correction(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> dict[str, Any] | None:
    """撤销人工修订并提交恢复 Tesseract 正文的异步重建。"""
    if not PDF_OCR_ENABLED:
        raise PdfOcrCorrectionValidationError("当前部署未启用 PDF OCR，无法撤销校对")

    with file_index_lock(user_id, knowledge_file_id):
        loaded = load_indexed_pdf_ocr_page(user_id, knowledge_file_id, page_number)
        if loaded is None:
            return None
        file_record, _, _ = loaded
        existing = get_pdf_ocr_correction(user_id, knowledge_file_id, page_number)
        if existing is None:
            raise PdfOcrCorrectionValidationError("该页面没有可撤销的人工修订")
        if delete_pdf_ocr_correction(user_id, knowledge_file_id, page_number) != 1:
            raise RuntimeError("OCR 人工修订撤销失败")
        previous_index_version = int(file_record.get("index_version") or 0)
        reset_record, job = enqueue_pdf_ocr_correction_index(
            user_id,
            file_record,
            page_number,
            "pdf_page_ocr_correction_deleted",
        )
        return {
            "file_id": str(knowledge_file_id),
            "page_number": page_number,
            "previous_index_version": previous_index_version,
            "index_version": int(reset_record["index_version"]),
            "has_correction": False,
            "job": job,
        }
