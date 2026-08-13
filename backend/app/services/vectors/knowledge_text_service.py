"""从 Milvus 读取知识文件 child/parent 文本与位置 metadata。"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.services.vectors.vector_store_factory import get_vector_store


def list_file_text_rows(
    *,
    user_id: int,
    file_id: UUID | str,
    index_version: int | None = None,
) -> list[dict[str, Any]]:
    """读取用户当前 Milvus collection 中单文件的有序 child 文本。"""
    records = get_vector_store(user_id=user_id).list_file_vectors(
        user_id=user_id,
        file_id=file_id,
    )
    rows: list[dict[str, Any]] = []
    for record in records:
        metadata = dict(record.document.metadata)
        row_version = int(metadata.get("index_version") or 0)
        if index_version is not None and row_version != index_version:
            continue
        rows.append({
            "chunk_id": record.id,
            "chunk_index": int(metadata.get("chunk_index") or 0),
            "index_version": row_version,
            "parent_id": str(metadata.get("parent_id") or ""),
            "parent_index": int(metadata.get("parent_index") or 0),
            "child_index": int(metadata.get("child_index") or 0),
            "content": record.document.page_content,
            "parent_content": str(metadata.get("parent_content") or ""),
            "metadata": metadata,
        })
    rows.sort(key=lambda row: (row["index_version"], row["chunk_index"]))
    return rows


def get_file_chunk_context(
    *,
    user_id: int,
    file_id: UUID | str,
    chunk_index: int,
    radius: int,
    index_version: int | None,
) -> list[dict[str, Any]]:
    """返回目标 child 及同一 parent 内的相邻 Milvus child。"""
    rows = list_file_text_rows(
        user_id=user_id,
        file_id=file_id,
        index_version=index_version,
    )
    targets = [row for row in rows if row["chunk_index"] == chunk_index]
    if not targets:
        return []
    target = max(targets, key=lambda row: row["index_version"])
    parent_id = target["parent_id"]
    context = [
        dict(row)
        for row in rows
        if row["index_version"] == target["index_version"]
        and abs(row["chunk_index"] - chunk_index) <= radius
        and (not parent_id or row["parent_id"] == parent_id)
    ]
    for row in context:
        row.update({
            "target_chunk_index": chunk_index,
            "target_parent_id": parent_id,
            "parent_metadata": target["metadata"],
        })
    return context


def get_pdf_page_rows(
    *,
    user_id: int,
    file_id: UUID | str,
    page_number: int,
    index_version: int,
) -> list[dict[str, Any]]:
    """读取指定 PDF 页的全部 Milvus child。"""
    return [
        row
        for row in list_file_text_rows(
            user_id=user_id,
            file_id=file_id,
            index_version=index_version,
        )
        if int(row["metadata"].get("page_number") or 0) == page_number
    ]


def get_pdf_page_ocr_metadata(
    *,
    user_id: int,
    file_id: UUID | str,
    page_number: int,
    index_version: int,
) -> dict[str, Any] | None:
    """读取指定 OCR 页面的首个 Milvus child metadata。"""
    for row in get_pdf_page_rows(
        user_id=user_id,
        file_id=file_id,
        page_number=page_number,
        index_version=index_version,
    ):
        if row["metadata"].get("pdf_parse_method") == "ocr":
            return row
    return None


def list_pdf_ocr_page_rows(
    *,
    user_id: int,
    file_id: UUID | str,
    index_version: int,
) -> list[dict[str, Any]]:
    """为每个 OCR 页返回一个代表 Milvus child。"""
    representatives: dict[int, dict[str, Any]] = {}
    for row in list_file_text_rows(
        user_id=user_id,
        file_id=file_id,
        index_version=index_version,
    ):
        metadata = row["metadata"]
        if metadata.get("pdf_parse_method") != "ocr":
            continue
        page_number = int(metadata.get("page_number") or 0)
        if page_number >= 1 and page_number not in representatives:
            representatives[page_number] = row
    return [representatives[key] for key in sorted(representatives)]


def select_rows_by_parent_ids(
    rows: Sequence[dict[str, Any]],
    parent_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """按 parent IDs 过滤内存行，供审计与测试复用。"""
    allowed = {str(parent_id) for parent_id in parent_ids}
    return [row for row in rows if row["parent_id"] in allowed]
