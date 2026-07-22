import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import (
    API_RATE_LIMIT_WINDOW_SECONDS,
    VECTOR_INDEX_MAX_BATCH_FILES,
    VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
)
from app.core.rate_limit import build_rate_limit_identifier, enforce_rate_limit
from app.core.security import get_current_user_id
from app.db.locks import file_index_lock
from app.repositories.knowledge_base_repository import knowledge_base_exists
from app.repositories.knowledge_chunk_repository import delete_file_chunks
from app.repositories.knowledge_file_repository import (
    get_knowledge_base_files_for_indexing,
    get_user_knowledge_file,
    reset_file_index_state,
    update_knowledge_file_status,
)
from app.repositories.vector_index_job_repository import (
    cancel_active_vector_index_jobs,
    get_user_vector_index_job,
    get_user_vector_index_job_health,
)
from app.schemas.knowledge import (
    ReindexPdfOcrPagesRequest,
    UpdatePdfOcrCorrectionRequest,
)
from app.services.documents.pdf_ocr_correction_service import (
    PdfOcrCorrectionConflictError,
    PdfOcrCorrectionValidationError,
    delete_pdf_ocr_page_correction,
    get_pdf_ocr_page_correction,
    save_pdf_ocr_page_correction,
)
from app.services.vectors.vector_index_queue_service import (
    enqueue_file_vector_index,
    serialize_vector_index_job_health,
    serialize_vector_index_job,
)
from app.services.vectors.embedding_settings_service import (
    get_effective_embedding_model_settings,
)
from app.services.vectors.vector_index_service import delete_file_vector_entries
from app.services.vectors.vector_worker_runtime_service import (
    get_vector_worker_runtime_summary,
)
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)
from app.services.documents.document_service import (
    ImageDocumentParseError,
    ensure_image_document_vision_settings,
    is_image_document_file_name,
)
from app.services.documents.pdf_ocr_reindex_service import (
    PdfOcrReindexConflictError,
    PdfOcrReindexValidationError,
    enqueue_pdf_page_ocr_reindex,
    enqueue_pdf_pages_ocr_reindex,
    retry_pdf_ocr_reindex_job,
)
from app.services.documents.pdf_ocr_quality_service import (
    PdfOcrQualityConflictError,
    PdfOcrQualityValidationError,
    get_pdf_ocr_quality_report,
)


router = APIRouter(prefix="/chat", tags=["vector-indexes"])
logger = logging.getLogger(__name__)


@router.get("/knowledge-files/{knowledge_file_id}/ocr/pages")
def get_knowledge_file_ocr_quality_report(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """读取当前用户单个 PDF 文件的 OCR 页面质量巡检清单。"""
    try:
        result = get_pdf_ocr_quality_report(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
        )
    except PdfOcrQualityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrQualityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"success": True, **result}


def ensure_user_embedding_settings(user_id: int) -> None:
    """确认当前用户已配置向量模型，避免提交无法执行的 worker 任务。"""
    try:
        get_effective_embedding_model_settings(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"向量模型配置无效：{exc}",
        ) from exc


def ensure_image_index_settings(
    user_id: int,
    file_records: Sequence[dict[str, Any]],
) -> None:
    """图片知识文件向量化前确认当前用户已配置 vision 模型。"""
    has_image_file = any(
        is_image_document_file_name(str(file_record.get("original_name") or ""))
        for file_record in file_records
    )
    if not has_image_file:
        return

    try:
        ensure_image_document_vision_settings(user_id)
    except ImageDocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge-files/{knowledge_file_id}/vectors")
def index_knowledge_file_vectors(
    request: Request,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """提交单个知识文件向量化任务。"""
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    ensure_image_index_settings(user_id, [dict(file_record)])

    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "向量化提交过于频繁，请稍后再试。",
    )

    job = enqueue_file_vector_index(
        file_record=file_record,
        user_id=user_id,
    )

    return {
        "success": True,
        "message": job.get("message") or "文件向量化任务已提交",
        "job": job,
    }


@router.post(
    "/knowledge-files/{knowledge_file_id}/ocr/pages/reindex",
)
def reindex_knowledge_file_ocr_pages(
    request: Request,
    payload: ReindexPdfOcrPagesRequest,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """提交多个扫描 PDF 页面的单批次异步 OCR 重新识别任务。"""
    if get_user_knowledge_file(user_id, knowledge_file_id) is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "向量化提交过于频繁，请稍后再试。",
    )
    try:
        result = enqueue_pdf_pages_ocr_reindex(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_numbers=payload.page_numbers,
        )
    except PdfOcrReindexValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrReindexConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "提交 PDF 批量 OCR 重新识别失败 user_id=%s file_id=%s",
            user_id,
            knowledge_file_id,
        )
        raise HTTPException(
            status_code=500,
            detail="提交批量 OCR 重新识别失败，请稍后重试。",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "success": True,
        "message": f"已提交 {result['page_count']} 页 OCR 重新识别批次",
        **result,
    }


@router.post(
    "/knowledge-files/{knowledge_file_id}/ocr/pages/{page_number}/reindex",
)
def reindex_knowledge_file_ocr_page(
    request: Request,
    knowledge_file_id: UUID,
    page_number: int,
    user_id: int = Depends(get_current_user_id),
):
    """提交指定扫描 PDF 页面的异步 OCR 重新识别任务。"""
    if get_user_knowledge_file(user_id, knowledge_file_id) is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "向量化提交过于频繁，请稍后再试。",
    )

    try:
        result = enqueue_pdf_page_ocr_reindex(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_number=page_number,
        )
    except PdfOcrReindexValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrReindexConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "提交 PDF 单页 OCR 重新识别失败 user_id=%s file_id=%s page=%s",
            user_id,
            knowledge_file_id,
            page_number,
        )
        raise HTTPException(
            status_code=500,
            detail="提交 OCR 重新识别失败，请稍后重试。",
        ) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "success": True,
        "message": f"第 {page_number} 页 OCR 重新识别任务已提交",
        **result,
    }


@router.post(
    "/knowledge-files/{knowledge_file_id}/ocr/reindex-jobs/{job_id}/retry",
)
def retry_knowledge_file_ocr_reindex_job(
    request: Request,
    knowledge_file_id: UUID,
    job_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """按失败 job 中保存的受控页码重新提交 OCR 批次。"""
    if get_user_knowledge_file(user_id, knowledge_file_id) is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "向量化提交过于频繁，请稍后再试。",
    )
    try:
        result = retry_pdf_ocr_reindex_job(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            job_id=job_id,
        )
    except PdfOcrReindexValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrReindexConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "重试 PDF OCR 批次失败 user_id=%s file_id=%s job_id=%s",
            user_id,
            knowledge_file_id,
            job_id,
        )
        raise HTTPException(
            status_code=500,
            detail="重试 OCR 重新识别失败，请稍后再试。",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "success": True,
        "message": f"已按原批次重试 {result['page_count']} 页 OCR 重新识别",
        **result,
    }


@router.get(
    "/knowledge-files/{knowledge_file_id}/ocr/pages/{page_number}/correction",
)
def get_knowledge_file_ocr_page_correction(
    knowledge_file_id: UUID,
    page_number: int,
    user_id: int = Depends(get_current_user_id),
):
    """读取指定 OCR 页面的完整文本和当前人工修订。"""
    try:
        result = get_pdf_ocr_page_correction(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_number=page_number,
        )
    except PdfOcrCorrectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrCorrectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"success": True, "correction": result}


@router.patch(
    "/knowledge-files/{knowledge_file_id}/ocr/pages/{page_number}/correction",
)
def update_knowledge_file_ocr_page_correction(
    request: Request,
    payload: UpdatePdfOcrCorrectionRequest,
    knowledge_file_id: UUID,
    page_number: int,
    user_id: int = Depends(get_current_user_id),
):
    """保存指定 OCR 页面的人工修订并异步重建索引。"""
    if get_user_knowledge_file(user_id, knowledge_file_id) is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "OCR 校对提交过于频繁，请稍后再试。",
    )
    try:
        result = save_pdf_ocr_page_correction(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_number=page_number,
            corrected_text=payload.corrected_text,
        )
    except PdfOcrCorrectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrCorrectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "保存 PDF OCR 人工修订失败 user_id=%s file_id=%s page=%s",
            user_id,
            knowledge_file_id,
            page_number,
        )
        raise HTTPException(
            status_code=500,
            detail="保存 OCR 人工修订失败，请稍后重试。",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "success": True,
        "message": f"第 {page_number} 页人工修订已保存，正在重建索引",
        "correction": result,
        "job": result["job"],
    }


@router.delete(
    "/knowledge-files/{knowledge_file_id}/ocr/pages/{page_number}/correction",
)
def delete_knowledge_file_ocr_page_correction(
    request: Request,
    knowledge_file_id: UUID,
    page_number: int,
    user_id: int = Depends(get_current_user_id),
):
    """撤销指定 OCR 页面的人工修订并异步恢复 OCR 索引。"""
    if get_user_knowledge_file(user_id, knowledge_file_id) is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ensure_user_embedding_settings(user_id)
    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "OCR 校对提交过于频繁，请稍后再试。",
    )
    try:
        result = delete_pdf_ocr_page_correction(
            user_id=user_id,
            knowledge_file_id=knowledge_file_id,
            page_number=page_number,
        )
    except PdfOcrCorrectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfOcrCorrectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "撤销 PDF OCR 人工修订失败 user_id=%s file_id=%s page=%s",
            user_id,
            knowledge_file_id,
            page_number,
        )
        raise HTTPException(
            status_code=500,
            detail="撤销 OCR 人工修订失败，请稍后重试。",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "success": True,
        "message": f"第 {page_number} 页人工修订已撤销，正在恢复 OCR 索引",
        "correction": result,
        "job": result["job"],
    }


@router.post("/knowledge-base/{knowledge_base_id}/vectors")
def index_knowledge_base_vectors(
    request: Request,
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """提交当前知识库下所有文件的向量化任务。"""
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    file_records = get_knowledge_base_files_for_indexing(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    if not file_records:
        return {
            "success": True,
            "knowledge_base_id": str(knowledge_base_id),
            "jobs": [],
            "message": "知识库中没有可向量化的文件",
        }
    ensure_user_embedding_settings(user_id)
    ensure_image_index_settings(
        user_id,
        [dict(file_record) for file_record in file_records],
    )

    if (
        VECTOR_INDEX_MAX_BATCH_FILES > 0
        and len(file_records) > VECTOR_INDEX_MAX_BATCH_FILES
    ):
        raise HTTPException(
            status_code=413,
            detail=(
                "单次向量化提交文件数量超过上限："
                f"当前 {len(file_records)} 个 / 上限 {VECTOR_INDEX_MAX_BATCH_FILES} 个。"
                "请分批处理或联系管理员调整配额。"
            ),
        )

    enforce_rate_limit(
        "vector-index",
        build_rate_limit_identifier(request, "user", user_id),
        VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS,
        API_RATE_LIMIT_WINDOW_SECONDS,
        "向量化提交过于频繁，请稍后再试。",
    )

    jobs = []
    for file_record in file_records:
        jobs.append(
            enqueue_file_vector_index(
                file_record=file_record,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
            )
        )

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "jobs": jobs,
    }


@router.get("/vector-index-jobs/health")
def get_vector_index_jobs_health(
    user_id: int = Depends(get_current_user_id),
):
    """查询当前用户向量化任务队列健康状态。"""
    health = get_user_vector_index_job_health(user_id)
    worker_runtime = get_vector_worker_runtime_summary()
    return {
        "success": True,
        **serialize_vector_index_job_health(health, worker_runtime),
    }


@router.get("/vector-index-jobs/{job_id}")
def get_vector_index_job(
    job_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """查询当前用户的向量化任务状态。"""
    job = get_user_vector_index_job(user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "success": True,
        "job": serialize_vector_index_job(job),
    }


@router.delete("/knowledge-files/{knowledge_file_id}/vectors")
def delete_knowledge_file_vectors(
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """删除单个知识文件的向量化存储。

    同时清理 Chroma 向量库和 PostgreSQL 全文检索分块，
    并将文件状态重置为 pending，允许重新向量化。
    """
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    normalized_file_id = str(knowledge_file_id)

    with file_index_lock(user_id, knowledge_file_id):
        # 1. 使尚未完成的旧任务失效，避免其在删除后再次写回数据。
        cancel_active_vector_index_jobs(
            user_id,
            knowledge_file_id,
            "用户删除了该文件的向量化结果",
        )

        # 2. 依次删除 Chroma 和 PostgreSQL 数据；任一失败都不发布 pending。
        try:
            delete_file_vector_entries(user_id, knowledge_file_id)
            chunks_deleted = delete_file_chunks(user_id, knowledge_file_id)
            reset_file_index_state(user_id, knowledge_file_id)
            invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
        except Exception as exc:
            # Chroma 已删除但 PG 清理失败时，标记 failed，避免读取半完成索引。
            update_knowledge_file_status(
                user_id,
                knowledge_file_id,
                "failed",
                expected_index_version=file_record["index_version"],
            )
            invalidate_file_knowledge_base_contexts(user_id, knowledge_file_id)
            logger.exception(
                "删除向量化存储失败 user_id=%s file_id=%s",
                user_id,
                knowledge_file_id,
            )
            raise HTTPException(
                status_code=500,
                detail="删除向量化存储失败，请稍后重试或检查向量库和数据库状态。",
            ) from exc

    return {
        "success": True,
        "message": "向量化存储已删除",
        "file_id": normalized_file_id,
        "chunks_deleted": chunks_deleted,
    }
