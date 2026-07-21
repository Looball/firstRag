"""扫描 PDF 单页异步重新识别编排。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import PDF_OCR_ENABLED
from app.db.locks import file_index_lock
from app.repositories.knowledge_chunk_repository import (
    get_user_pdf_page_ocr_metadata,
)
from app.repositories.knowledge_file_repository import (
    get_user_knowledge_file,
    reset_file_index_state,
    update_knowledge_file_status,
)
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


def enqueue_pdf_page_ocr_reindex(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> dict[str, Any] | None:
    """校验目标 OCR 页，递增索引版本并提交强制页异步任务。"""
    if page_number < 1:
        raise PdfOcrReindexValidationError("PDF 页码必须从 1 开始")
    if not PDF_OCR_ENABLED:
        raise PdfOcrReindexValidationError("当前部署未启用 PDF OCR，无法重新识别")

    with file_index_lock(user_id, knowledge_file_id):
        file_record = get_user_knowledge_file(user_id, knowledge_file_id)
        if file_record is None:
            return None
        if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
            raise PdfOcrReindexValidationError("只有 PDF 文件支持单页 OCR 重新识别")
        if file_record["status"] != "indexed":
            raise PdfOcrReindexConflictError(
                "文件正在处理或尚未完成索引，请等待当前任务结束后重试",
            )

        index_version = int(file_record.get("index_version") or 0)
        page_chunk = get_user_pdf_page_ocr_metadata(
            user_id=user_id,
            file_id=knowledge_file_id,
            page_number=page_number,
            index_version=index_version,
        )
        if page_chunk is None:
            raise PdfOcrReindexValidationError("PDF 页面不存在或尚未建立索引")
        metadata = page_chunk.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("pdf_parse_method") != "ocr":
            raise PdfOcrReindexValidationError("该页面使用原生文本，不需要 OCR 重新识别")

        reset_record = reset_file_index_state(user_id, knowledge_file_id)
        if reset_record is None:
            return None
        updated_record = {
            **dict(file_record),
            **dict(reset_record),
        }
        try:
            job = enqueue_file_vector_index(
                file_record=updated_record,
                user_id=user_id,
                job_options={
                    "trigger": "pdf_page_ocr_reindex",
                    "force_ocr_page_numbers": [page_number],
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
            "page_number": page_number,
            "previous_index_version": index_version,
            "index_version": int(reset_record["index_version"]),
            "job": job,
        }
