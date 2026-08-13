#!/usr/bin/env python3
"""重建并审计 Milvus v3 文本 collection。

完整审计结果用于为移除 PostgreSQL chunk 表放行。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import sleep
from typing import Any
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs/evals/latest_milvus_text_cutover.json"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import UPLOAD_ROOT  # noqa: E402
from app.db.executor import execute, fetch_all, fetch_one  # noqa: E402
from app.db.locks import file_index_lock  # noqa: E402
from app.repositories.pdf_ocr_correction_repository import (  # noqa: E402
    list_pdf_ocr_corrections,
)
from app.repositories.pdf_ocr_history_repository import (  # noqa: E402
    get_latest_pdf_ocr_attempts,
)
from app.services.vectors.vector_index_service import (  # noqa: E402
    index_file_vectors,
)
from app.services.vectors.vector_store import VectorRecord  # noqa: E402
from app.services.vectors.vector_store_factory import (  # noqa: E402
    get_vector_store,
)


class CutoverError(RuntimeError):
    """Milvus 文本切换未满足安全门禁。"""


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild indexed files into Milvus v3 and record the audit rows "
            "required by migration 011."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rebuild source files. Without it, only audit existing v3 data.",
    )
    parser.add_argument(
        "--file-id",
        action="append",
        default=[],
        help="Limit the operation to one file UUID. Can be repeated.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Write a JSON report without document text or credentials.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="Per-file attempts for transient provider or Milvus failures.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=12.0,
        help="Delay between retries; default exceeds local Milvus flush rate window.",
    )
    return parser


def list_indexed_files(file_ids: list[str]) -> list[dict[str, Any]]:
    """查询仍有效且状态为 indexed 的知识文件。"""
    params: list[object] = []
    filter_sql = ""
    if file_ids:
        normalized_ids = [str(UUID(value)) for value in file_ids]
        filter_sql = " AND id = ANY(%s::uuid[])"
        params.append(normalized_ids)
    return fetch_all(
        f"""
        SELECT
            id,
            user_id,
            original_name,
            storage_path,
            status,
            index_version
        FROM knowledge_files
        WHERE deleted_at IS NULL
          AND status = 'indexed'
          {filter_sql}
        ORDER BY user_id, created_at, id;
        """,
        tuple(params),
    )


def require_cutover_audit_table() -> None:
    """确认 migration 010 已创建审计表。"""
    row = fetch_one(
        "SELECT to_regclass('public.milvus_text_cutover_audits') AS table_name;"
    )
    if not row or row.get("table_name") is None:
        raise CutoverError(
            "缺少 milvus_text_cutover_audits；请先应用 migration 010。"
        )


def resolve_storage_path(raw_path: str) -> Path:
    """把宿主机历史 uploads 路径映射为当前 runtime 的 uploads mount。"""
    source = Path(raw_path)
    if source.is_file():
        return source

    parts = source.parts
    if "uploads" in parts:
        uploads_index = parts.index("uploads")
        mapped = UPLOAD_ROOT.joinpath(*parts[uploads_index + 1 :])
        if mapped.is_file():
            return mapped

    basename_candidate = UPLOAD_ROOT / source.name
    if basename_candidate.is_file():
        return basename_candidate
    raise FileNotFoundError(f"知识文件源文件不存在：{source.name}")


def build_content_digest(records: list[VectorRecord]) -> str:
    """计算不泄露正文的稳定 child/parent 文本审计摘要。"""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item.id):
        metadata = record.document.metadata
        for value in (
            record.id,
            record.document.page_content,
            str(metadata.get("parent_id") or ""),
            str(metadata.get("parent_content") or ""),
        ):
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def audit_records(
    *,
    records: list[VectorRecord],
    user_id: int,
    file_id: str,
    index_version: int,
    expected_count: int | None,
) -> dict[str, Any]:
    """验证单文件 v3 entities 的身份、版本和两层文本完整性。"""
    if not records:
        raise CutoverError("Milvus 中没有该文件的 v3 entities")
    if expected_count is not None and len(records) != expected_count:
        detail = f"expected={expected_count}, actual={len(records)}"
        raise CutoverError(f"Milvus entity count 不匹配：{detail}")
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise CutoverError("Milvus child_id 存在重复")

    parent_ids: set[str] = set()
    for record in records:
        metadata = record.document.metadata
        if int(metadata.get("user_id") or 0) != user_id:
            raise CutoverError("Milvus entity user_id 不匹配")
        if str(metadata.get("file_id") or "") != file_id:
            raise CutoverError("Milvus entity file_id 不匹配")
        if int(metadata.get("index_version") or 0) != index_version:
            raise CutoverError("Milvus entity index_version 不匹配")
        if not record.document.page_content.strip():
            raise CutoverError("Milvus child content 为空")
        parent_id = str(metadata.get("parent_id") or "")
        parent_content = str(metadata.get("parent_content") or "")
        if not parent_id or not parent_content.strip():
            raise CutoverError("Milvus parent identity 或 parent_content 为空")
        parent_ids.add(parent_id)

    return {
        "chunk_count": len(records),
        "parent_count": len(parent_ids),
        "content_sha256": build_content_digest(records),
    }


def record_cutover_audit(
    *,
    file_id: str,
    user_id: int,
    index_version: int,
    collection_name: str,
    audit: dict[str, Any],
) -> None:
    """写入 migration 011 使用的无正文 cutover 证明。"""
    execute(
        """
        INSERT INTO milvus_text_cutover_audits (
            knowledge_file_id,
            user_id,
            index_version,
            collection_name,
            chunk_count,
            content_sha256,
            audited_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (knowledge_file_id) DO UPDATE
        SET
            user_id = EXCLUDED.user_id,
            index_version = EXCLUDED.index_version,
            collection_name = EXCLUDED.collection_name,
            chunk_count = EXCLUDED.chunk_count,
            content_sha256 = EXCLUDED.content_sha256,
            audited_at = now();
        """,
        (
            file_id,
            user_id,
            index_version,
            collection_name,
            audit["chunk_count"],
            audit["content_sha256"],
        ),
    )


def process_file(file_record: dict[str, Any], execute_rebuild: bool) -> dict[str, Any]:
    """可选重建单文件，随后读取 Milvus 做完整性审计。"""
    file_id = str(file_record["id"])
    user_id = int(file_record["user_id"])
    index_version = int(file_record["index_version"])
    expected_count: int | None = None

    with file_index_lock(user_id, file_id):
        vector_store = get_vector_store(user_id=user_id)
        existing_records = vector_store.list_file_vectors(
            user_id=user_id,
            file_id=file_id,
        )
        try:
            existing_audit = audit_records(
                records=existing_records,
                user_id=user_id,
                file_id=file_id,
                index_version=index_version,
                expected_count=None,
            )
        except CutoverError:
            existing_audit = None
        if existing_audit is not None:
            record_cutover_audit(
                file_id=file_id,
                user_id=user_id,
                index_version=index_version,
                collection_name=vector_store.collection_name,
                audit=existing_audit,
            )
            return {
                "file_id": file_id,
                "user_id": user_id,
                "index_version": index_version,
                "collection_name": vector_store.collection_name,
                "rebuilt": False,
                "reused_existing_v3": True,
                **existing_audit,
            }

        if not execute_rebuild:
            raise CutoverError("Milvus 中没有可复用的完整 v3 entities")

        if execute_rebuild:
            source_path = resolve_storage_path(str(file_record["storage_path"]))
            correction_rows = list_pdf_ocr_corrections(user_id, file_id)
            result = index_file_vectors(
                user_id=user_id,
                file_id=file_id,
                storage_path=source_path,
                index_version=index_version,
                original_name=str(file_record["original_name"]),
                pdf_ocr_corrections={
                    int(row["page_number"]): dict(row)
                    for row in correction_rows
                },
                previous_ocr_attempts=get_latest_pdf_ocr_attempts(
                    user_id,
                    file_id,
                ),
                job_trigger="milvus_text_cutover",
                record_ocr_history=False,
            )
            expected_count = int(result["chunk_count"])

        records = vector_store.list_file_vectors(
            user_id=user_id,
            file_id=file_id,
        )
        audit = audit_records(
            records=records,
            user_id=user_id,
            file_id=file_id,
            index_version=index_version,
            expected_count=expected_count,
        )
        record_cutover_audit(
            file_id=file_id,
            user_id=user_id,
            index_version=index_version,
            collection_name=vector_store.collection_name,
            audit=audit,
        )
    return {
        "file_id": file_id,
        "user_id": user_id,
        "index_version": index_version,
        "collection_name": vector_store.collection_name,
        "rebuilt": execute_rebuild,
        "reused_existing_v3": False,
        **audit,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    """原子写入不包含正文和凭据的 JSON 报告。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def main() -> int:
    """执行全部指定文件的重建与审计。"""
    args = build_parser().parse_args()
    require_cutover_audit_table()
    files = list_indexed_files(args.file_id)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    if args.retry_attempts < 1:
        raise CutoverError("retry attempts 必须至少为 1")
    if args.retry_delay_seconds < 0:
        raise CutoverError("retry delay 不能为负数")
    for file_record in files:
        file_id = str(file_record["id"])
        last_error: Exception | None = None
        for attempt in range(1, args.retry_attempts + 1):
            try:
                result = process_file(file_record, args.execute)
                results.append(result)
                print(
                    f"PASS file_id={file_id} "
                    f"rebuilt={str(result['rebuilt']).lower()}"
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < args.retry_attempts and args.execute:
                    print(
                        f"RETRY file_id={file_id} attempt={attempt}: {exc}",
                        file=sys.stderr,
                    )
                    sleep(args.retry_delay_seconds)
                    continue
                break
        if last_error is not None:
            failures.append({"file_id": file_id, "error": str(last_error)})
            print(f"FAIL file_id={file_id}: {last_error}", file=sys.stderr)

    report = {
        "success": not failures,
        "execute": bool(args.execute),
        "indexed_file_count": len(files),
        "passed_file_count": len(results),
        "failed_file_count": len(failures),
        "results": results,
        "failures": failures,
    }
    write_report(args.report, report)
    print(
        "Milvus text cutover audit: "
        f"passed={len(results)} failed={len(failures)} report={args.report}"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
