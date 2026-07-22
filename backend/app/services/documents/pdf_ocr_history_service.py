"""PDF 页级 OCR 识别历史查询与趋势汇总。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE
from app.repositories.knowledge_chunk_repository import (
    get_user_pdf_page_ocr_metadata,
)
from app.repositories.knowledge_file_repository import get_user_knowledge_file
from app.repositories.pdf_ocr_history_repository import (
    list_pdf_ocr_page_history,
)


class PdfOcrHistoryValidationError(ValueError):
    """文件或页码不支持 OCR 历史查询时抛出。"""


class PdfOcrHistoryConflictError(RuntimeError):
    """文件状态不允许查询当前 OCR 历史时抛出。"""


def _normalize_confidence(value: object) -> float | None:
    """把数据库置信度规范化为 0-100 两位小数。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(min(100.0, max(0.0, float(value))), 2)


def _build_delta(current: float | None, previous: float | None) -> float | None:
    """计算相邻 OCR 置信度变化，没有任一分数时返回空。"""
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def get_pdf_ocr_page_history_report(
    user_id: int,
    knowledge_file_id: UUID,
    page_number: int,
) -> dict[str, Any] | None:
    """返回当前用户指定 PDF 页面的 OCR 历史和相邻变化。"""
    if page_number < 1:
        raise PdfOcrHistoryValidationError("PDF 页码必须从 1 开始")

    file_record = get_user_knowledge_file(user_id, knowledge_file_id)
    if file_record is None:
        return None
    if Path(str(file_record["original_name"])).suffix.lower() != ".pdf":
        raise PdfOcrHistoryValidationError("只有 PDF 文件支持 OCR 识别历史")
    if file_record["status"] != "indexed":
        raise PdfOcrHistoryConflictError(
            "文件正在处理或尚未完成索引，请等待当前任务结束后重试",
        )

    index_version = int(file_record.get("index_version") or 0)
    current_page = get_user_pdf_page_ocr_metadata(
        user_id=user_id,
        file_id=knowledge_file_id,
        page_number=page_number,
        index_version=index_version,
    )
    if current_page is None:
        raise PdfOcrHistoryValidationError("指定页面不存在或不是 OCR 页面")

    limit = max(1, PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE)
    rows = list_pdf_ocr_page_history(
        user_id=user_id,
        knowledge_file_id=knowledge_file_id,
        page_number=page_number,
        limit=limit,
    )
    runs: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        previous = rows[index + 1] if index + 1 < len(rows) else None
        confidence = _normalize_confidence(row.get("ocr_confidence"))
        previous_confidence = (
            _normalize_confidence(previous.get("ocr_confidence"))
            if previous is not None
            else None
        )
        runs.append({
            "id": str(row["id"]),
            "index_version": int(row["index_version"]),
            "ocr_attempt": int(row["ocr_attempt"]),
            "source_job_id": (
                str(row["source_job_id"])
                if row.get("source_job_id") is not None
                else None
            ),
            "trigger": str(row["trigger"]),
            "ocr_engine": str(row["ocr_engine"]),
            "ocr_confidence": confidence,
            "ocr_quality": str(row["ocr_quality"]),
            "ocr_word_count": int(row["ocr_word_count"]),
            "ocr_text": str(row["ocr_text"]),
            "ocr_text_sha256": str(row["ocr_text_sha256"]),
            "ocr_text_source": str(row["ocr_text_source"]),
            "correction_revision": (
                int(row["correction_revision"])
                if row.get("correction_revision") is not None
                else None
            ),
            "created_at": row.get("created_at"),
            "previous_run_id": (
                str(previous["id"]) if previous is not None else None
            ),
            "confidence_delta": _build_delta(
                confidence,
                previous_confidence,
            ),
            "word_count_delta": (
                int(row["ocr_word_count"])
                - int(previous["ocr_word_count"])
                if previous is not None
                else None
            ),
            "text_changed": (
                str(row["ocr_text_sha256"])
                != str(previous["ocr_text_sha256"])
                if previous is not None
                else None
            ),
        })

    deltas = [
        run["confidence_delta"]
        for run in runs
        if run["confidence_delta"] is not None
    ]
    confidences = [
        run["ocr_confidence"]
        for run in runs
        if run["ocr_confidence"] is not None
    ]
    return {
        "file": {
            "id": str(file_record["id"]),
            "original_name": str(file_record["original_name"]),
            "index_version": index_version,
        },
        "page_number": page_number,
        "summary": {
            "run_count": len(runs),
            "retention_limit": limit,
            "latest_confidence": (
                runs[0]["ocr_confidence"] if runs else None
            ),
            "latest_delta": (
                runs[0]["confidence_delta"] if runs else None
            ),
            "best_confidence": max(confidences) if confidences else None,
            "improved_count": sum(1 for delta in deltas if delta > 0),
            "degraded_count": sum(1 for delta in deltas if delta < 0),
            "unchanged_count": sum(1 for delta in deltas if delta == 0),
        },
        "runs": runs,
    }
