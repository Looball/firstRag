"""文件级 PDF OCR 页面质量巡检服务。"""

from pathlib import Path
import re
from typing import Any
from uuid import UUID

from app.core.config import PDF_OCR_REINDEX_MAX_BATCH_PAGES
from app.repositories.knowledge_chunk_repository import (
    list_user_pdf_ocr_page_rows,
)
from app.repositories.knowledge_file_repository import get_user_knowledge_file
from app.repositories.pdf_ocr_correction_repository import (
    list_pdf_ocr_corrections,
)


OCR_PAGE_EXCERPT_MAX_CHARACTERS = 220


class PdfOcrQualityValidationError(ValueError):
    """文件不支持 OCR 质量巡检时抛出。"""


class PdfOcrQualityConflictError(RuntimeError):
    """文件当前索引状态不允许巡检时抛出。"""


def _normalize_confidence(value: object) -> float | None:
    """将 metadata 置信度限制在 Tesseract 0-100 分数范围。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(min(100.0, max(0.0, float(value))), 2)


def _normalize_page_number(value: object) -> int | None:
    """只接受大于零的整型页码。"""
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 1 else None


def _normalize_positive_int(value: object, default: int = 1) -> int:
    """把内部计数 metadata 规范化为正整数。"""
    normalized = _normalize_page_number(value)
    return normalized if normalized is not None else default


def _build_excerpt(value: object) -> str:
    """折叠空白并截断代表 chunk，避免列表返回完整页面正文。"""
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(normalized) <= OCR_PAGE_EXCERPT_MAX_CHARACTERS:
        return normalized
    return f"{normalized[:OCR_PAGE_EXCERPT_MAX_CHARACTERS].rstrip()}…"


def get_pdf_ocr_quality_report(
    user_id: int,
    knowledge_file_id: UUID,
) -> dict[str, Any] | None:
    """汇总当前用户文件当前索引版本的 OCR 页面质量。"""
    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        return None
    if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
        raise PdfOcrQualityValidationError("只有 PDF 文件支持 OCR 质量巡检")
    if file_record["status"] != "indexed":
        raise PdfOcrQualityConflictError(
            "文件正在处理或尚未完成索引，请等待当前任务结束后重试",
        )

    index_version = int(file_record.get("index_version") or 0)
    page_rows = list_user_pdf_ocr_page_rows(
        user_id=user_id,
        file_id=knowledge_file_id,
        index_version=index_version,
    )
    correction_rows = list_pdf_ocr_corrections(user_id, knowledge_file_id)
    corrections = {
        int(row["page_number"]): row
        for row in correction_rows
        if _normalize_page_number(row.get("page_number")) is not None
    }

    pages: list[dict[str, Any]] = []
    document_page_count = 0
    for row in page_rows:
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            continue
        page_number = _normalize_page_number(metadata.get("page_number"))
        if page_number is None:
            continue
        page_count = _normalize_page_number(metadata.get("page_count"))
        document_page_count = max(
            document_page_count,
            page_count or page_number,
        )
        correction = corrections.get(page_number)
        confidence = _normalize_confidence(metadata.get("ocr_confidence"))
        quality = str(metadata.get("ocr_quality") or "unknown")
        has_correction = correction is not None
        pages.append({
            "page_number": page_number,
            "page_count": page_count,
            "chunk_index": int(row["chunk_index"]),
            "index_version": int(row["index_version"]),
            "ocr_confidence": confidence,
            "ocr_quality": quality,
            "ocr_attempt": _normalize_positive_int(metadata.get("ocr_attempt")),
            "needs_review": quality == "low" and not has_correction,
            "has_correction": has_correction,
            "correction_revision": (
                int(correction["revision"]) if correction is not None else 0
            ),
            "correction_updated_at": (
                correction.get("updated_at") if correction is not None else None
            ),
            "excerpt": _build_excerpt(row.get("content")),
        })

    pages.sort(key=lambda page: (
        not page["needs_review"],
        page["ocr_confidence"] is None,
        page["ocr_confidence"] if page["ocr_confidence"] is not None else 101,
        page["page_number"],
    ))
    confidences = [
        float(page["ocr_confidence"])
        for page in pages
        if page["ocr_confidence"] is not None
    ]
    return {
        "file": {
            "id": str(file_record["id"]),
            "original_name": str(file_record["original_name"]),
            "status": str(file_record["status"]),
            "index_version": index_version,
        },
        "summary": {
            "document_page_count": document_page_count,
            "ocr_page_count": len(pages),
            "needs_review_count": sum(
                1 for page in pages if page["needs_review"]
            ),
            "low_confidence_count": sum(
                1 for page in pages if page["ocr_quality"] == "low"
            ),
            "corrected_count": sum(
                1 for page in pages if page["has_correction"]
            ),
            "average_confidence": (
                round(sum(confidences) / len(confidences), 2)
                if confidences
                else None
            ),
            "max_reindex_pages": max(1, PDF_OCR_REINDEX_MAX_BATCH_PAGES),
        },
        "pages": pages,
    }
