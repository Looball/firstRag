import hashlib
import logging
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_SSL,
    PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE,
    VECTOR_STORE_PATH,
)
from app.db.locks import file_index_lock
from app.db.executor import Row
from app.repositories.knowledge_chunk_repository import (
    delete_file_chunks,
    list_user_pdf_ocr_page_history_rows,
    replace_file_chunks,
)
from app.repositories.knowledge_file_repository import update_knowledge_file_status
from app.repositories.pdf_ocr_correction_repository import (
    list_pdf_ocr_corrections,
)
from app.repositories.pdf_ocr_history_repository import (
    get_latest_pdf_ocr_attempts,
    record_pdf_ocr_history_entries,
)
from app.services.documents.document_service import (
    EmptyDocumentError,
    load_document,
    split_documents,
)
from app.services.knowledge_profile_cache import (
    invalidate_file_knowledge_base_contexts,
)
from app.services.vectors.embedding_model import create_embedding_model_from_settings
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
    get_effective_embedding_model_settings,
)


logger = logging.getLogger(__name__)
OCR_HISTORY_TEXT_MAX_CHARACTERS = 100_000


def get_force_ocr_page_numbers(options: object) -> set[int]:
    """从内部 job options 提取正整数 OCR 页码，忽略异常字段。"""
    if not isinstance(options, dict):
        return set()
    page_numbers = options.get("force_ocr_page_numbers")
    if not isinstance(page_numbers, list):
        return set()
    return {
        page_number
        for page_number in page_numbers
        if isinstance(page_number, int)
        and not isinstance(page_number, bool)
        and page_number >= 1
    }


def _normalize_ocr_history_confidence(value: object) -> float | None:
    """将内部 OCR confidence 规范化为数据库约束允许的分数。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(min(100.0, max(0.0, float(value))), 2)


def _normalize_ocr_history_positive_int(
    value: object,
    default: int,
) -> int:
    """规范化 OCR attempt、word count 和 correction revision。"""
    if isinstance(value, bool):
        return default
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return normalized if normalized >= 1 else default


def _build_pdf_ocr_history_entry(
    *,
    page_number: int,
    index_version: int,
    metadata: dict[str, Any],
    ocr_text: str,
    source_job_id: UUID | str | None,
    trigger: str,
    text_source: str,
) -> dict[str, Any]:
    """从页级 metadata 构造受约束、可持久化的 OCR 历史记录。"""
    normalized_text = ocr_text[:OCR_HISTORY_TEXT_MAX_CHARACTERS]
    quality = str(metadata.get("ocr_quality") or "unknown")
    if quality not in {"good", "low", "unknown"}:
        quality = "unknown"
    word_count = metadata.get("ocr_word_count")
    normalized_word_count = (
        int(word_count)
        if isinstance(word_count, int)
        and not isinstance(word_count, bool)
        and word_count >= 0
        else 0
    )
    correction_revision = metadata.get("ocr_correction_revision")
    normalized_revision = (
        _normalize_ocr_history_positive_int(correction_revision, 1)
        if correction_revision is not None
        else None
    )
    return {
        "page_number": page_number,
        "index_version": index_version,
        "ocr_attempt": _normalize_ocr_history_positive_int(
            metadata.get("ocr_attempt"),
            1,
        ),
        "source_job_id": str(source_job_id) if source_job_id else None,
        "trigger": (trigger.strip() or "file_index")[:64],
        "ocr_engine": str(metadata.get("ocr_engine") or "tesseract")[:64],
        "ocr_confidence": _normalize_ocr_history_confidence(
            metadata.get("ocr_confidence"),
        ),
        "ocr_quality": quality,
        "ocr_word_count": normalized_word_count,
        "ocr_text": normalized_text,
        "ocr_text_sha256": hashlib.sha256(
            normalized_text.encode("utf-8"),
        ).hexdigest(),
        "ocr_text_source": (text_source.strip() or "tesseract")[:32],
        "correction_revision": normalized_revision,
    }


def build_pdf_ocr_history_entries(
    documents: list[Document],
    index_version: int,
    source_job_id: UUID | str | None,
    trigger: str,
) -> list[dict[str, Any]]:
    """提取本次解析的页级原始 OCR 文本，并移除内部 metadata。"""
    entries: list[dict[str, Any]] = []
    for document in documents:
        metadata = document.metadata
        raw_ocr_text = metadata.pop("_ocr_history_text", None)
        if metadata.get("pdf_parse_method") != "ocr":
            continue
        page_number = metadata.get("page_number")
        if (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            continue
        entries.append(_build_pdf_ocr_history_entry(
            page_number=page_number,
            index_version=index_version,
            metadata=metadata,
            ocr_text=str(raw_ocr_text or ""),
            source_job_id=source_job_id,
            trigger=trigger,
            text_source="tesseract",
        ))
    return entries


def _backfill_legacy_pdf_ocr_history(
    user_id: int,
    file_id: UUID | str,
    index_version: int,
    existing_attempts: dict[int, int],
) -> dict[int, int]:
    """从上一版 chunks 衔接迁移前的 OCR baseline 和 attempt。"""
    if index_version <= 0:
        return existing_attempts

    previous_rows = list_user_pdf_ocr_page_history_rows(
        user_id=user_id,
        file_id=file_id,
        index_version=index_version - 1,
    )
    baseline_entries: list[dict[str, Any]] = []
    merged_attempts = dict(existing_attempts)
    for row in previous_rows:
        metadata = row.get("metadata")
        page_number = row.get("page_number")
        if (
            not isinstance(metadata, dict)
            or isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            continue
        attempt = _normalize_ocr_history_positive_int(
            metadata.get("ocr_attempt"),
            1,
        )
        merged_attempts[page_number] = max(
            merged_attempts.get(page_number, 0),
            attempt,
        )
        if page_number in existing_attempts:
            continue
        baseline_entries.append(_build_pdf_ocr_history_entry(
            page_number=page_number,
            index_version=int(row["index_version"]),
            metadata=metadata,
            ocr_text=str(row.get("content") or ""),
            source_job_id=None,
            trigger="legacy_snapshot",
            text_source=str(metadata.get("ocr_text_source") or "legacy_chunk"),
        ))

    record_pdf_ocr_history_entries(
        user_id=user_id,
        knowledge_file_id=file_id,
        entries=baseline_entries,
        max_runs_per_page=PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE,
    )
    return merged_attempts


def _normalize_collection_name_part(value: str) -> str:
    """将 collection 名称片段规范化为 Chroma 可接受的安全字符。"""
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    normalized = normalized.strip("-_")
    return normalized or "collection"


def build_user_vector_collection_name(
    base_collection_name: str,
    user_id: int,
    settings: EmbeddingModelSettings,
) -> str:
    """按用户和 embedding 配置生成隔离的 Chroma collection 名称。"""
    identity = "|".join([
        str(user_id),
        settings.provider,
        settings.model,
        str(settings.dimensions or ""),
    ])
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    base = _normalize_collection_name_part(base_collection_name)[:24]
    collection_name = f"{base}-u{user_id}-{digest}"
    return collection_name[:63].strip("-_") or f"u{user_id}-{digest}"


def get_vector_store(
    user_id: int | None = None,
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> Chroma:
    """创建 Chroma 向量库连接；Compose 使用 HTTP，单进程本地可嵌入。"""
    resolved_collection_name = collection_name
    embedding_function = None
    if user_id is not None:
        settings = get_effective_embedding_model_settings(user_id)
        resolved_collection_name = build_user_vector_collection_name(
            collection_name,
            user_id,
            settings,
        )
        embedding_function = create_embedding_model_from_settings(settings)

    common_options = {
        "collection_name": resolved_collection_name,
        "embedding_function": embedding_function,
    }
    if CHROMA_HOST:
        return Chroma(
            **common_options,
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            ssl=CHROMA_SSL,
        )

    return Chroma(
        **common_options,
        persist_directory=str(persist_directory),
    )


def build_chunk_ids(chunks: list[Document]) -> list[str]:
    """为分块生成稳定向量 ID，避免同一文件重复入库。"""
    chunk_ids = []
    for chunk in chunks:
        user_id = chunk.metadata["user_id"]
        file_id = chunk.metadata["file_id"]
        chunk_index = chunk.metadata["chunk_index"]
        index_version = chunk.metadata["index_version"]
        chunk_ids.append(f"{user_id}:{file_id}:v{index_version}:{chunk_index}")
    return chunk_ids


def build_file_vector_filter(user_id: int, file_id: UUID | str) -> dict:
    """构造删除单个文件所有 Chroma 向量的 metadata 条件。"""
    return {
        "$and": [
            {"user_id": str(user_id)},
            {"file_id": str(file_id)},
        ]
    }


def delete_file_vector_entries(
    user_id: int,
    file_id: UUID | str,
    vectordb: Chroma | None = None,
) -> None:
    """删除单个文件在 Chroma 中的全部索引版本。"""
    if vectordb is not None:
        resolved_vectordb = vectordb
    else:
        try:
            resolved_vectordb = get_vector_store(user_id=user_id)
        except ValueError:
            # 兼容迁移前的旧 collection 清理：删除操作不应要求用户先配置 Key。
            resolved_vectordb = get_vector_store()
    resolved_vectordb.delete(where=build_file_vector_filter(user_id, file_id))


def compensate_failed_file_index(
    user_id: int,
    file_id: UUID | str,
    vectordb: Chroma | None = None,
) -> None:
    """尽力清除一次失败索引留下的 Chroma 与全文检索分块。"""
    try:
        delete_file_vector_entries(user_id, file_id, vectordb)
    except Exception:
        logger.exception("补偿清理 Chroma 向量失败 file_id=%s", file_id)

    try:
        delete_file_chunks(user_id, file_id)
    except Exception:
        logger.exception("补偿清理全文分块失败 file_id=%s", file_id)


def index_file_vectors(
    user_id: int,
    file_id: UUID | str,
    storage_path: str | Path,
    index_version: int,
    original_name: str | None = None,
    persist_directory: str | Path = VECTOR_STORE_PATH,
    collection_name: str = CHROMA_COLLECTION_NAME,
    force_ocr_page_numbers: set[int] | None = None,
    pdf_ocr_corrections: dict[int, dict[str, object]] | None = None,
    previous_ocr_attempts: dict[int, int] | None = None,
    source_job_id: UUID | str | None = None,
    job_trigger: str = "file_index",
) -> dict[str, Any]:
    """将单个知识文件解析、切分并写入 Chroma。"""
    file_path = Path(storage_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    documents = load_document(
        file_path=file_path,
        file_id=file_id,
        user_id=user_id,
        original_name=original_name or file_path.name,
        force_ocr_page_numbers=force_ocr_page_numbers,
        pdf_ocr_corrections=pdf_ocr_corrections,
        previous_ocr_attempts=previous_ocr_attempts,
    )
    ocr_history_entries = build_pdf_ocr_history_entries(
        documents=documents,
        index_version=index_version,
        source_job_id=source_job_id,
        trigger=job_trigger,
    )
    chunks = split_documents(documents)
    if not chunks:
        raise EmptyDocumentError("文件为空，未解析出可入库的文本分块")

    for chunk in chunks:
        chunk.metadata["index_version"] = index_version

    normalized_file_id = str(file_id)
    vectordb: Chroma | None = None
    try:
        vectordb = get_vector_store(
            user_id=user_id,
            persist_directory=persist_directory,
            collection_name=collection_name,
        )
        delete_file_vector_entries(user_id, file_id, vectordb)
        chunk_ids = build_chunk_ids(chunks)
        vectordb.add_documents(
            documents=chunks,
            ids=chunk_ids,
        )
        replace_file_chunks(
            user_id=user_id,
            file_id=file_id,
            index_version=index_version,
            chunks=chunks,
            chunk_ids=chunk_ids,
        )
        record_pdf_ocr_history_entries(
            user_id=user_id,
            knowledge_file_id=file_id,
            entries=ocr_history_entries,
            max_runs_per_page=PDF_OCR_HISTORY_MAX_RUNS_PER_PAGE,
        )
    except Exception:
        # 两套存储不能参与同一事务；失败时清空半成品并保持 failed 状态。
        compensate_failed_file_index(
            user_id,
            file_id,
            vectordb,
        )
        raise

    actual_collection_name = getattr(
        getattr(vectordb, "_collection", None),
        "name",
        collection_name,
    )
    return {
        "file_id": normalized_file_id,
        "chunk_count": len(chunks),
        "character_count": sum(
            len(chunk.page_content)
            for chunk in chunks
        ),
        "collection_name": actual_collection_name,
        "persist_directory": str(persist_directory),
        "force_ocr_page_numbers": sorted(force_ocr_page_numbers or set()),
        "ocr_correction_page_numbers": sorted(
            (pdf_ocr_corrections or {}).keys(),
        ),
        "ocr_history_entry_count": len(ocr_history_entries),
    }


def index_knowledge_file_record(
    file_record: Row | dict[str, Any],
    user_id: int,
    index_version: int,
    job_options: dict[str, Any] | None = None,
    source_job_id: UUID | str | None = None,
) -> dict[str, Any]:
    """索引单条知识文件记录，并同步文件处理状态。

    API 层只负责权限校验和 HTTP 错误转换；文件解析、切分、向量入库、
    全文 chunk 入库和文件状态流转统一放在这里。
    """
    file_id = file_record["id"]
    with file_index_lock(user_id, file_id):
        # 删除接口会先递增版本；旧任务取得锁后不会写入已失效的数据。
        if not update_knowledge_file_status(
            user_id,
            file_id,
            "indexing",
            expected_index_version=index_version,
        ):
            raise RuntimeError("索引任务版本已过期")
        invalidate_file_knowledge_base_contexts(user_id, file_id)

        try:
            previous_ocr_attempts = get_latest_pdf_ocr_attempts(
                user_id,
                file_id,
            )
            previous_ocr_attempts = _backfill_legacy_pdf_ocr_history(
                user_id=user_id,
                file_id=file_id,
                index_version=index_version,
                existing_attempts=previous_ocr_attempts,
            )
            correction_rows = list_pdf_ocr_corrections(user_id, file_id)
            pdf_ocr_corrections = {
                int(row["page_number"]): dict(row)
                for row in correction_rows
            }
            index_result = index_file_vectors(
                user_id=user_id,
                file_id=file_id,
                storage_path=file_record["storage_path"],
                index_version=index_version,
                original_name=str(file_record["original_name"]),
                force_ocr_page_numbers=get_force_ocr_page_numbers(job_options),
                pdf_ocr_corrections=pdf_ocr_corrections,
                previous_ocr_attempts=previous_ocr_attempts,
                source_job_id=source_job_id,
                job_trigger=(
                    str(job_options.get("trigger") or "file_index")
                    if isinstance(job_options, dict)
                    else "file_index"
                ),
            )
        except Exception:
            update_knowledge_file_status(
                user_id,
                file_id,
                "failed",
                expected_index_version=index_version,
            )
            invalidate_file_knowledge_base_contexts(user_id, file_id)
            raise

        if not update_knowledge_file_status(
            user_id,
            file_id,
            "indexed",
            expected_index_version=index_version,
        ):
            raise RuntimeError("索引任务版本已过期")
        invalidate_file_knowledge_base_contexts(user_id, file_id)
    return {
        "id": str(file_id),
        "original_name": file_record["original_name"],
        "status": "indexed",
        **index_result,
    }
