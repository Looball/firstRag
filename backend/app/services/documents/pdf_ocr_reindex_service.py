"""扫描 PDF 单页与多页批次异步重新识别编排。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import (
    PDF_OCR_ENABLED,
    PDF_OCR_REINDEX_MAX_BATCH_PAGES,
)
from app.db.locks import file_index_lock
from app.repositories.knowledge_chunk_repository import list_user_pdf_ocr_page_rows
from app.repositories.knowledge_file_repository import (
    get_user_knowledge_file,
    reset_file_index_state,
    update_knowledge_file_status,
)
from app.repositories.vector_index_job_repository import get_user_vector_index_job
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
)


class PdfOcrReindexValidationError(ValueError):
    """文件、页码或 OCR metadata 不允许重新识别时抛出。"""


class PdfOcrReindexConflictError(RuntimeError):
    """文件当前状态不允许开始新的重新识别任务时抛出。"""


def _normalize_page_numbers(page_numbers: list[int]) -> list[int]:
    """校验、去重并排序批量 OCR 页码。"""
    if not page_numbers:
        raise PdfOcrReindexValidationError("请至少选择一个 OCR 页面")
    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        or page_number < 1
        for page_number in page_numbers
    ):
        raise PdfOcrReindexValidationError("PDF 页码必须为从 1 开始的整数")

    normalized = sorted(set(page_numbers))
    max_batch_pages = max(1, PDF_OCR_REINDEX_MAX_BATCH_PAGES)
    if len(normalized) > max_batch_pages:
        raise PdfOcrReindexValidationError(
            "单次 OCR 重新识别页面超过上限："
            f"当前 {len(normalized)} 页 / 上限 {max_batch_pages} 页",
        )
    return normalized


def _get_indexed_ocr_page_numbers(
    user_id: int,
    knowledge_file_id: UUID,
    index_version: int,
) -> set[int]:
    """读取当前索引版本中可重新识别的 OCR 页码。"""
    page_numbers: set[int] = set()
    for row in list_user_pdf_ocr_page_rows(
        user_id=user_id,
        file_id=knowledge_file_id,
        index_version=index_version,
    ):
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_page_number = metadata.get("page_number")
        if isinstance(raw_page_number, bool):
            continue
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError):
            continue
        if page_number >= 1:
            page_numbers.add(page_number)
    return page_numbers


def enqueue_pdf_pages_ocr_reindex(
    user_id: int,
    knowledge_file_id: UUID,
    page_numbers: list[int],
) -> dict[str, Any] | None:
    """校验多个 OCR 页并以一次文件重建任务提交。"""
    normalized_page_numbers = _normalize_page_numbers(page_numbers)
    if not PDF_OCR_ENABLED:
        raise PdfOcrReindexValidationError("当前部署未启用 PDF OCR，无法重新识别")

    with file_index_lock(user_id, knowledge_file_id):
        file_record = get_user_knowledge_file(user_id, knowledge_file_id)
        if file_record is None:
            return None
        if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
            raise PdfOcrReindexValidationError("只有 PDF 文件支持 OCR 重新识别")
        if file_record["status"] != "indexed":
            raise PdfOcrReindexConflictError(
                "文件正在处理或尚未完成索引，请等待当前任务结束后重试",
            )

        index_version = int(file_record.get("index_version") or 0)
        indexed_ocr_pages = _get_indexed_ocr_page_numbers(
            user_id,
            knowledge_file_id,
            index_version,
        )
        invalid_pages = [
            page_number
            for page_number in normalized_page_numbers
            if page_number not in indexed_ocr_pages
        ]
        if invalid_pages:
            invalid_label = "、".join(str(page) for page in invalid_pages)
            raise PdfOcrReindexValidationError(
                f"第 {invalid_label} 页不存在或不是 OCR 页面",
            )

        reset_record = reset_file_index_state(user_id, knowledge_file_id)
        if reset_record is None:
            return None
        updated_record = {**dict(file_record), **dict(reset_record)}
        trigger = (
            "pdf_page_ocr_reindex"
            if len(normalized_page_numbers) == 1
            else "pdf_pages_ocr_reindex"
        )
        try:
            job = enqueue_file_vector_index(
                file_record=updated_record,
                user_id=user_id,
                job_options={
                    "trigger": trigger,
                    "force_ocr_page_numbers": normalized_page_numbers,
                },
            )
        except Exception:
            update_knowledge_file_status(
                user_id,
                knowledge_file_id,
                "failed",
                expected_index_version=reset_record["index_version"],
            )
            invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
            raise

        invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
        return {
            "file_id": str(knowledge_file_id),
            "page_numbers": normalized_page_numbers,
            "page_count": len(normalized_page_numbers),
            "previous_index_version": index_version,
            "index_version": int(reset_record["index_version"]),
            "job": job,
        }


def enqueue_pdf_page_ocr_reindex(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> dict[str, Any] | None:
    """兼容单页入口，并复用批量 OCR 重新识别编排。"""
    result = enqueue_pdf_pages_ocr_reindex(
        user_id=user_id,
        knowledge_file_id=knowledge_file_id,
        page_numbers=[page_number],
    )
    if result is not None:
        result["page_number"] = page_number
    return result


def retry_pdf_ocr_reindex_job(
    user_id: int,
    knowledge_file_id: UUID,
    job_id: UUID,
) -> dict[str, Any] | None:
    """使用失败 job 的受控页码与当前版本重新排队。"""
    with file_index_lock(user_id, knowledge_file_id):
        file_record = get_user_knowledge_file(user_id, knowledge_file_id)
        if file_record is None:
            return None
        if not PDF_OCR_ENABLED:
            raise PdfOcrReindexValidationError("当前部署未启用 PDF OCR，无法重新识别")
        if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
            raise PdfOcrReindexValidationError("只有 PDF 文件支持 OCR 重新识别")
        failed_job = get_user_vector_index_job(user_id, job_id)
        if (
            failed_job is None
            or str(failed_job.get("knowledge_file_id")) != str(knowledge_file_id)
        ):
            raise PdfOcrReindexValidationError("OCR 重新识别任务不存在")
        if failed_job.get("status") != "failed":
            raise PdfOcrReindexConflictError("只有失败的 OCR 重新识别任务可以重试")

        options = failed_job.get("options")
        if not isinstance(options, dict) or options.get("trigger") not in {
            "pdf_page_ocr_reindex",
            "pdf_pages_ocr_reindex",
        }:
            raise PdfOcrReindexValidationError("该任务不是可重试的 OCR 重新识别批次")
        raw_page_numbers = options.get("force_ocr_page_numbers")
        if not isinstance(raw_page_numbers, list):
            raise PdfOcrReindexValidationError("OCR 重新识别任务缺少有效页码")
        page_numbers = _normalize_page_numbers(raw_page_numbers)

        current_version = int(file_record.get("index_version") or 0)
        if int(failed_job.get("index_version") or 0) != current_version:
            raise PdfOcrReindexConflictError("任务版本已过期，请重新打开 OCR 巡检")
        if file_record.get("status") != "failed":
            raise PdfOcrReindexConflictError("文件当前状态不允许重试该任务")
        if not update_knowledge_file_status(
            user_id,
            knowledge_file_id,
            "pending",
            expected_index_version=current_version,
        ):
            raise PdfOcrReindexConflictError("文件状态已变化，请刷新后重试")

        updated_record = {**dict(file_record), "status": "pending"}
        try:
            job = enqueue_file_vector_index(
                file_record=updated_record,
                user_id=user_id,
                job_options={
                    "trigger": options["trigger"],
                    "force_ocr_page_numbers": page_numbers,
                },
            )
        except Exception:
            update_knowledge_file_status(
                user_id,
                knowledge_file_id,
                "failed",
                expected_index_version=current_version,
            )
            invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
            raise

        invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
        return {
            "file_id": str(knowledge_file_id),
            "page_numbers": page_numbers,
            "page_count": len(page_numbers),
            "index_version": current_version,
            "retried_job_id": str(job_id),
            "job": job,
        }
