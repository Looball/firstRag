"""可审计、可恢复且不调用 embedding provider 的 Chroma 到 Milvus 迁移工具。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_SSL,
    MILVUS_COLLECTION_PREFIX,
    MILVUS_CONSISTENCY_LEVEL,
    MILVUS_DATABASE,
    MILVUS_TIMEOUT_SECONDS,
    MILVUS_TOKEN,
    MILVUS_URI,
    PROJECT_ROOT,
    VECTOR_STORE_PATH,
)
from app.core.sensitive_data import sanitize_sensitive_text
from app.repositories.vector_migration_repository import (
    count_active_vector_index_jobs,
    list_vector_migration_chunk_rows,
)
from app.services.vectors.chroma_vector_store import ChromaVectorStore
from app.services.vectors.embedding_settings_service import (
    EmbeddingModelSettings,
    normalize_embedding_provider,
    resolve_embedding_model_name,
)
from app.services.vectors.milvus_vector_store import MilvusVectorStore
from app.services.vectors.vector_store import VectorRecord, VectorStoreBoundary
from app.services.vectors.vector_store_factory import (
    build_milvus_user_collection_name,
    build_milvus_user_collection_prefix,
    build_user_vector_collection_name,
)


CHECKPOINT_VERSION = 1
REPORT_VERSION = 1
DEFAULT_CHECKPOINT_PATH = PROJECT_ROOT / "tmp/vector-migration/checkpoint.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "tmp/vector-migration/report.json"


class MigrationValidationError(RuntimeError):
    """携带稳定 machine-readable code 的迁移验证错误。"""

    def __init__(self, code: str, message: str) -> None:
        """保存错误 code 与不含正文、embedding 的安全说明。"""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class MigrationChunkFact:
    """PostgreSQL 中一条 current chunk 的迁移事实。"""

    chunk_id: str
    user_id: int
    file_id: str
    index_version: int
    chunk_index: int
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MigrationFilePlan:
    """以 user/file/embedding identity 为单位的迁移计划。"""

    user_id: int
    file_id: str
    file_status: str
    file_index_version: int
    settings: EmbeddingModelSettings | None
    source_collection: str | None
    target_collection: str | None
    chunks: tuple[MigrationChunkFact, ...]

    @property
    def key(self) -> str:
        """返回 checkpoint 使用的稳定文件键。"""
        return f"{self.user_id}:{self.file_id}"


@dataclass(frozen=True)
class ValidatedSource:
    """已通过 PostgreSQL 对账且包含可导入 embeddings 的 Chroma 文件。"""

    records: tuple[VectorRecord, ...]
    dimensions: int
    digest: str


@dataclass
class MigrationStorePair:
    """同一 identity 的 Chroma source 与 Milvus target。"""

    source: VectorStoreBoundary
    target: MilvusVectorStore
    close: Callable[[], None]


@dataclass(frozen=True)
class MigrationOptions:
    """一次迁移或 rollback-check 的运行参数。"""

    dry_run: bool
    rollback_check: bool
    batch_size: int
    sleep_seconds: float
    sample_top_k: int
    checkpoint_path: Path
    report_path: Path


def _utc_now() -> str:
    """返回便于审计的 UTC ISO 时间。"""
    return datetime.now(UTC).isoformat()


def _as_float(value: object, default: float = 60.0) -> float:
    """把数据库 NUMERIC 或普通数值转成 float。"""
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _identity_settings(row: Mapping[str, Any]) -> EmbeddingModelSettings | None:
    """只从非敏感字段构造 collection identity，不读取或解密 API Key。"""
    raw_provider = str(row.get("embedding_provider") or "").strip()
    raw_model = str(row.get("embedding_model") or "").strip()
    if not raw_provider or not raw_model:
        return None
    provider = normalize_embedding_provider(raw_provider)
    model = resolve_embedding_model_name(provider, raw_model)
    raw_dimensions = row.get("embedding_dimensions")
    dimensions = int(raw_dimensions) if raw_dimensions is not None else None
    return EmbeddingModelSettings(
        provider=provider,
        model=model,
        api_key="",
        base_url=None,
        dimensions=dimensions,
        timeout_seconds=_as_float(row.get("embedding_timeout_seconds")),
        max_retries=int(row.get("embedding_max_retries") or 2),
    )


def build_migration_file_plans(
    rows: Iterable[Mapping[str, Any]],
) -> list[MigrationFilePlan]:
    """把数据库行分组为确定顺序的文件计划，保留缺设置文件供失败清单。"""
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["user_id"]), str(row["file_id"]))].append(row)

    plans: list[MigrationFilePlan] = []
    for (user_id, file_id), file_rows in sorted(grouped.items()):
        first = file_rows[0]
        settings = _identity_settings(first)
        source_collection = (
            build_user_vector_collection_name(
                CHROMA_COLLECTION_NAME,
                user_id,
                settings,
            )
            if settings is not None
            else None
        )
        target_collection = (
            build_milvus_user_collection_name(
                MILVUS_COLLECTION_PREFIX,
                user_id,
                settings,
            )
            if settings is not None
            else None
        )
        chunks = tuple(MigrationChunkFact(
            chunk_id=str(row["chunk_id"]),
            user_id=user_id,
            file_id=file_id,
            index_version=int(row["index_version"]),
            chunk_index=int(row["chunk_index"]),
            content=str(row["content"]),
            metadata=dict(row.get("metadata") or {}),
        ) for row in file_rows)
        plans.append(MigrationFilePlan(
            user_id=user_id,
            file_id=file_id,
            file_status=str(first.get("file_status") or ""),
            file_index_version=int(first.get("file_index_version") or 0),
            settings=settings,
            source_collection=source_collection,
            target_collection=target_collection,
            chunks=chunks,
        ))
    return plans


def _normalize_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """统一 Chroma/Milvus 核心字段类型，保留其它 metadata 原值。"""
    normalized = dict(metadata)
    if "user_id" in normalized:
        normalized["user_id"] = str(normalized["user_id"])
    if "file_id" in normalized:
        normalized["file_id"] = str(normalized["file_id"])
    for field_name in ("chunk_index", "index_version"):
        if field_name in normalized:
            normalized[field_name] = int(normalized[field_name])
    normalized.pop("chunk_id", None)
    return normalized


def _document_signature(document: Document) -> str:
    """以不可逆摘要比较 Top-K，不把正文写入报告。"""
    payload = json.dumps(
        {
            "content": document.page_content,
            "metadata": _normalize_metadata(document.metadata),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_digest(records: Sequence[VectorRecord]) -> str:
    """生成可审计但不暴露正文或向量数值的 source fingerprint。"""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item.id):
        digest.update(record.id.encode("utf-8"))
        digest.update(_document_signature(record.document).encode("ascii"))
        for value in record.embedding or []:
            digest.update(float(value).hex().encode("ascii"))
    return digest.hexdigest()


def _validate_plan(plan: MigrationFilePlan) -> None:
    """拒绝没有 identity、非 indexed 或 PostgreSQL 版本漂移的文件。"""
    if plan.settings is None:
        raise MigrationValidationError(
            "missing_embedding_identity",
            "用户缺少可用于定位 current Chroma collection 的 embedding 设置",
        )
    if plan.file_status != "indexed":
        raise MigrationValidationError(
            "file_not_indexed",
            f"文件状态不是 indexed：{plan.file_status or 'unknown'}",
        )
    if not plan.chunks:
        raise MigrationValidationError("empty_postgres_file", "PostgreSQL 文件无 chunk")
    if any(
        chunk.index_version != plan.file_index_version
        for chunk in plan.chunks
    ):
        raise MigrationValidationError(
            "postgres_index_version_mismatch",
            "PostgreSQL chunk 与 knowledge file index_version 不一致",
        )
    ids = [chunk.chunk_id for chunk in plan.chunks]
    if len(ids) != len(set(ids)):
        raise MigrationValidationError("duplicate_postgres_id", "PostgreSQL chunk ID 重复")


def validate_source_records(
    plan: MigrationFilePlan,
    records: Sequence[VectorRecord],
) -> ValidatedSource:
    """对账 Chroma 与 PostgreSQL，并验证所有既有 embeddings 可导入。"""
    _validate_plan(plan)
    expected = {chunk.chunk_id: chunk for chunk in plan.chunks}
    actual = {record.id: record for record in records}
    if len(records) != len(actual):
        raise MigrationValidationError("duplicate_chroma_id", "Chroma 返回重复 ID")
    if set(actual) != set(expected):
        raise MigrationValidationError(
            "chroma_id_mismatch",
            (
                "Chroma/PostgreSQL ID 集合不一致："
                f"missing={len(set(expected) - set(actual))} "
                f"unexpected={len(set(actual) - set(expected))}"
            ),
        )

    dimensions: int | None = None
    for chunk_id, fact in expected.items():
        record = actual[chunk_id]
        if record.document.page_content != fact.content:
            raise MigrationValidationError(
                "chroma_content_mismatch",
                "Chroma/PostgreSQL 正文不一致",
            )
        metadata = _normalize_metadata(record.document.metadata)
        expected_core = {
            "user_id": str(fact.user_id),
            "file_id": fact.file_id,
            "chunk_index": fact.chunk_index,
            "index_version": fact.index_version,
        }
        if any(metadata.get(key) != value for key, value in expected_core.items()):
            raise MigrationValidationError(
                "chroma_metadata_mismatch",
                "Chroma/PostgreSQL 核心 metadata 不一致",
            )
        embedding = record.embedding
        if embedding is None:
            raise MigrationValidationError(
                "chroma_embedding_missing",
                "Chroma entry 无法读取 embedding",
            )
        current_dimensions = len(embedding)
        if current_dimensions < 2:
            raise MigrationValidationError(
                "invalid_embedding_dimension",
                "Chroma embedding dimension 必须大于 1",
            )
        if dimensions is None:
            dimensions = current_dimensions
        if current_dimensions != dimensions:
            raise MigrationValidationError(
                "mixed_embedding_dimensions",
                "同一 Chroma collection/file 存在混合 dimensions",
            )
        if any(not math.isfinite(float(value)) for value in embedding):
            raise MigrationValidationError(
                "non_finite_embedding",
                "Chroma embedding 包含非有限值",
            )
        if not any(float(value) != 0.0 for value in embedding):
            raise MigrationValidationError("zero_embedding", "Chroma embedding 是零向量")

    assert dimensions is not None
    if plan.settings and (
        plan.settings.dimensions is not None
        and plan.settings.dimensions != dimensions
    ):
        raise MigrationValidationError(
            "settings_dimension_mismatch",
            "Chroma 实际 dimension 与用户 embedding 设置不一致",
        )
    ordered = tuple(actual[chunk.chunk_id] for chunk in plan.chunks)
    return ValidatedSource(
        records=ordered,
        dimensions=dimensions,
        digest=_source_digest(ordered),
    )


def validate_target_records(
    source: ValidatedSource,
    target_records: Sequence[VectorRecord],
) -> None:
    """验证 Milvus 完整保留 ID、正文、metadata、dimension 和向量数值。"""
    expected = {record.id: record for record in source.records}
    actual = {record.id: record for record in target_records}
    if len(target_records) != len(actual) or set(actual) != set(expected):
        raise MigrationValidationError(
            "milvus_id_mismatch",
            (
                "Milvus/Chroma ID 集合不一致："
                f"missing={len(set(expected) - set(actual))} "
                f"unexpected={len(set(actual) - set(expected))}"
            ),
        )
    for chunk_id, source_record in expected.items():
        target_record = actual[chunk_id]
        if target_record.document.page_content != source_record.document.page_content:
            raise MigrationValidationError(
                "milvus_content_mismatch",
                "Milvus/Chroma 正文不一致",
            )
        if _normalize_metadata(target_record.document.metadata) != _normalize_metadata(
            source_record.document.metadata,
        ):
            raise MigrationValidationError(
                "milvus_metadata_mismatch",
                "Milvus/Chroma metadata 不一致",
            )
        source_embedding = source_record.embedding or []
        target_embedding = target_record.embedding or []
        if len(target_embedding) != source.dimensions:
            raise MigrationValidationError(
                "milvus_dimension_mismatch",
                "Milvus/Chroma embedding dimension 不一致",
            )
        if any(
            not math.isclose(float(left), float(right), rel_tol=1e-6, abs_tol=1e-6)
            for left, right in zip(source_embedding, target_embedding, strict=True)
        ):
            raise MigrationValidationError(
                "milvus_embedding_mismatch",
                "Milvus 未完整保留 Chroma embedding 数值",
            )


def compare_top_k(
    *,
    plan: MigrationFilePlan,
    source: ValidatedSource,
    source_store: VectorStoreBoundary,
    target_store: VectorStoreBoundary,
    k: int,
) -> dict[str, Any]:
    """用 stored embedding 对比 Chroma/Milvus file-filtered Top-K。"""
    sample_count = min(3, len(source.records))
    resolved_k = min(k, len(source.records))
    overlaps: list[float] = []
    top1_matches = 0
    self_hits = 0
    for record in source.records[:sample_count]:
        embedding = record.embedding or []
        source_results = source_store.search_vectors(
            query_embedding=embedding,
            user_id=plan.user_id,
            file_ids=[plan.file_id],
            k=resolved_k,
        ).results
        target_results = target_store.search_vectors(
            query_embedding=embedding,
            user_id=plan.user_id,
            file_ids=[plan.file_id],
            k=resolved_k,
        ).results
        if not source_results or not target_results:
            raise MigrationValidationError(
                "ann_empty_result",
                "Chroma 或 Milvus filtered ANN 未返回候选",
            )
        source_signatures = [
            _document_signature(result.document)
            for result in source_results
        ]
        target_signatures = [
            _document_signature(result.document)
            for result in target_results
        ]
        expected_signature = _document_signature(record.document)
        if source_signatures[0] == expected_signature and target_signatures[0] == expected_signature:
            self_hits += 1
        if source_signatures[0] == target_signatures[0]:
            top1_matches += 1
        overlaps.append(
            len(set(source_signatures) & set(target_signatures)) / resolved_k,
        )
    if self_hits != sample_count:
        raise MigrationValidationError(
            "ann_self_hit_failed",
            "Chroma/Milvus stored-vector filtered ANN self-hit 未全部通过",
        )
    return {
        "sample_count": sample_count,
        "top_k": resolved_k,
        "self_hits": self_hits,
        "top1_matches": top1_matches,
        "mean_overlap": round(sum(overlaps) / len(overlaps), 6),
    }


def verify_source_ann(
    *,
    plan: MigrationFilePlan,
    source: ValidatedSource,
    source_store: VectorStoreBoundary,
    k: int,
) -> dict[str, Any]:
    """在 rollback-check 中只读验证 Chroma filtered ANN 原路径。"""
    sample_count = min(3, len(source.records))
    self_hits = 0
    for record in source.records[:sample_count]:
        results = source_store.search_vectors(
            query_embedding=record.embedding or [],
            user_id=plan.user_id,
            file_ids=[plan.file_id],
            k=min(k, len(source.records)),
        ).results
        if results and _document_signature(results[0].document) == _document_signature(
            record.document,
        ):
            self_hits += 1
    if self_hits != sample_count:
        raise MigrationValidationError(
            "chroma_ann_self_hit_failed",
            "Chroma rollback filtered ANN self-hit 未全部通过",
        )
    return {"sample_count": sample_count, "self_hits": self_hits}


def _scope_fingerprint(plans: Sequence[MigrationFilePlan]) -> str:
    """绑定 checkpoint 到确定 PostgreSQL 事实集合，防止错误续跑。"""
    digest = hashlib.sha256()
    for plan in plans:
        digest.update(plan.key.encode("utf-8"))
        digest.update(str(plan.source_collection).encode("utf-8"))
        digest.update(str(plan.target_collection).encode("utf-8"))
        for chunk in plan.chunks:
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(hashlib.sha256(chunk.content.encode("utf-8")).digest())
            digest.update(str(chunk.index_version).encode("ascii"))
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """在同目录原子替换 JSON，避免中断留下半个 checkpoint/report。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def _load_checkpoint(path: Path, scope: str) -> dict[str, Any]:
    """读取同 scope checkpoint；不同事实集合必须显式使用新路径。"""
    if not path.exists():
        return {
            "version": CHECKPOINT_VERSION,
            "scope_fingerprint": scope,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "files": {},
        }
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    if checkpoint.get("version") != CHECKPOINT_VERSION:
        raise MigrationValidationError(
            "checkpoint_version_mismatch",
            "checkpoint version 不兼容",
        )
    if checkpoint.get("scope_fingerprint") != scope:
        raise MigrationValidationError(
            "checkpoint_scope_mismatch",
            "PostgreSQL 事实集合已变化，请使用新的 checkpoint 路径",
        )
    return checkpoint


def validate_backup_manifest(path: Path) -> dict[str, Any]:
    """验证真实导入前的 PostgreSQL/uploads/Chroma 备份审计清单。"""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationValidationError(
            "invalid_backup_manifest",
            "无法读取 backup manifest",
        ) from exc
    if manifest.get("version") != 1 or manifest.get("verified") is not True:
        raise MigrationValidationError(
            "unverified_backup_manifest",
            "backup manifest 必须是 version=1 且 verified=true",
        )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise MigrationValidationError("invalid_backup_manifest", "缺少备份 artifacts")
    for name in ("postgres", "uploads", "chroma", "milvus"):
        artifact = artifacts.get(name)
        if (
            not isinstance(artifact, dict)
            or artifact.get("verified") is not True
            or not str(artifact.get("location") or "").strip()
        ):
            raise MigrationValidationError(
                "unverified_backup_artifact",
                f"备份清单缺少已验证 artifact：{name}",
            )
    return {
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "created_at": manifest.get("created_at"),
    }


def _failure_entry(
    plan: MigrationFilePlan,
    stage: str,
    exc: Exception,
) -> dict[str, Any]:
    """生成不会包含正文、embedding 或 credential 的结构化失败项。"""
    code = exc.code if isinstance(exc, MigrationValidationError) else "unexpected_error"
    return {
        "user_id": plan.user_id,
        "file_id": plan.file_id,
        "source_collection": plan.source_collection,
        "target_collection": plan.target_collection,
        "stage": stage,
        "code": code,
        "message": sanitize_sensitive_text(str(exc))[:500],
        "reindex_required": True,
    }


def run_migration(
    *,
    plans: Sequence[MigrationFilePlan],
    store_factory: Callable[[MigrationFilePlan], MigrationStorePair],
    options: MigrationOptions,
    backup_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """执行 dry-run、可恢复 import 或只读 rollback-check，并持续写审计结果。"""
    started_at = _utc_now()
    scope = _scope_fingerprint(plans)
    checkpoint = (
        _load_checkpoint(options.checkpoint_path, scope)
        if not options.dry_run and not options.rollback_check
        else None
    )
    file_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    completed = skipped = 0

    for plan in plans:
        stage = "source_validation"
        pair: MigrationStorePair | None = None
        imported = False
        try:
            pair = store_factory(plan)
            source = validate_source_records(
                plan,
                pair.source.list_file_vectors(
                    user_id=plan.user_id,
                    file_id=plan.file_id,
                    include_embeddings=True,
                ),
            )
            result: dict[str, Any] = {
                "user_id": plan.user_id,
                "file_id": plan.file_id,
                "source_collection": plan.source_collection,
                "target_collection": plan.target_collection,
                "entries": len(source.records),
                "dimensions": source.dimensions,
                "source_digest": source.digest,
            }
            if options.dry_run:
                result["status"] = "planned"
                file_results.append(result)
                completed += 1
                continue
            if options.rollback_check:
                stage = "rollback_ann_validation"
                result["ann"] = verify_source_ann(
                    plan=plan,
                    source=source,
                    source_store=pair.source,
                    k=options.sample_top_k,
                )
                source_after = validate_source_records(
                    plan,
                    pair.source.list_file_vectors(
                        user_id=plan.user_id,
                        file_id=plan.file_id,
                        include_embeddings=True,
                    ),
                )
                if source_after.digest != source.digest:
                    raise MigrationValidationError(
                        "chroma_changed_during_rollback_check",
                        "rollback-check 前后 Chroma fingerprint 发生变化",
                    )
                result["status"] = "rollback_ready"
                result["source_unchanged"] = True
                file_results.append(result)
                completed += 1
                continue

            checkpoint_file = (checkpoint or {}).get("files", {}).get(plan.key, {})
            if checkpoint_file.get("status") == "completed":
                stage = "resume_target_validation"
                target_records = pair.target.list_file_vectors(
                    user_id=plan.user_id,
                    file_id=plan.file_id,
                    include_embeddings=True,
                )
                try:
                    validate_target_records(source, target_records)
                except MigrationValidationError:
                    pass
                else:
                    result["ann"] = compare_top_k(
                        plan=plan,
                        source=source,
                        source_store=pair.source,
                        target_store=pair.target,
                        k=options.sample_top_k,
                    )
                    result["status"] = "resumed_verified"
                    file_results.append(result)
                    skipped += 1
                    continue

            stage = "milvus_import"
            pair.target.import_file_vectors(
                user_id=plan.user_id,
                file_id=plan.file_id,
                documents=[record.document for record in source.records],
                ids=[record.id for record in source.records],
                embeddings=[record.embedding or [] for record in source.records],
                batch_size=options.batch_size,
            )
            imported = True
            stage = "target_validation"
            validate_target_records(
                source,
                pair.target.list_file_vectors(
                    user_id=plan.user_id,
                    file_id=plan.file_id,
                    include_embeddings=True,
                ),
            )
            stage = "top_k_comparison"
            result["ann"] = compare_top_k(
                plan=plan,
                source=source,
                source_store=pair.source,
                target_store=pair.target,
                k=options.sample_top_k,
            )
            result["status"] = "completed"
            file_results.append(result)
            completed += 1
            assert checkpoint is not None
            checkpoint["files"][plan.key] = {
                "status": "completed",
                "entries": len(source.records),
                "dimensions": source.dimensions,
                "source_digest": source.digest,
                "source_collection": plan.source_collection,
                "target_collection": plan.target_collection,
                "completed_at": _utc_now(),
            }
            checkpoint["updated_at"] = _utc_now()
            _write_json_atomic(options.checkpoint_path, checkpoint)
        except Exception as exc:
            if imported and pair is not None:
                try:
                    pair.target.delete_imported_file_vectors(
                        user_id=plan.user_id,
                        file_id=plan.file_id,
                    )
                except Exception:
                    pass
            failure = _failure_entry(plan, stage, exc)
            failures.append(failure)
            file_results.append({**failure, "status": "failed"})
            if checkpoint is not None:
                checkpoint["files"][plan.key] = {
                    "status": "failed",
                    "stage": stage,
                    "code": failure["code"],
                    "updated_at": _utc_now(),
                }
                checkpoint["updated_at"] = _utc_now()
                _write_json_atomic(options.checkpoint_path, checkpoint)
        finally:
            if pair is not None:
                pair.close()
        if options.sleep_seconds > 0:
            time.sleep(options.sleep_seconds)

    mode = "rollback-check" if options.rollback_check else "migrate"
    report = {
        "version": REPORT_VERSION,
        "mode": mode,
        "dry_run": options.dry_run,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "scope_fingerprint": scope,
        "backup_evidence": dict(backup_evidence or {}),
        "summary": {
            "files_total": len(plans),
            "files_completed": completed,
            "files_resumed_verified": skipped,
            "files_failed": len(failures),
            "entries_total": sum(len(plan.chunks) for plan in plans),
        },
        "files": file_results,
        "failures": failures,
        "reindex_required": [
            {
                "user_id": failure["user_id"],
                "file_id": failure["file_id"],
                "reason": failure["code"],
                "source_collection": failure["source_collection"],
            }
            for failure in failures
        ],
        "rollback": {
            "recommended_provider": "chroma" if options.rollback_check else None,
            "source_modified": False,
        },
    }
    _write_json_atomic(options.report_path, report)
    return report


def _create_store_pair(plan: MigrationFilePlan) -> MigrationStorePair:
    """按计划显式创建 Chroma source 与无 credential 的 Milvus target。"""
    if plan.settings is None or not plan.source_collection or not plan.target_collection:
        raise MigrationValidationError(
            "missing_embedding_identity",
            "无法创建 source/target collection identity",
        )
    chroma_options: dict[str, Any] = {
        "collection_name": plan.source_collection,
        "embedding_function": None,
        "create_collection_if_not_exists": False,
    }
    if CHROMA_HOST:
        chroma_client = Chroma(
            **chroma_options,
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            ssl=CHROMA_SSL,
        )
    else:
        chroma_client = Chroma(
            **chroma_options,
            persist_directory=str(VECTOR_STORE_PATH),
        )

    from pymilvus import MilvusClient

    milvus_client = MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        db_name=MILVUS_DATABASE,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )
    target = MilvusVectorStore(
        client=milvus_client,
        collection_name=plan.target_collection,
        user_collection_prefix=build_milvus_user_collection_prefix(
            MILVUS_COLLECTION_PREFIX,
            plan.user_id,
        ),
        embedding_model=None,
        dimensions=plan.settings.dimensions,
        timeout_seconds=MILVUS_TIMEOUT_SECONDS,
        consistency_level=MILVUS_CONSISTENCY_LEVEL,
    )
    return MigrationStorePair(
        source=ChromaVectorStore(chroma_client, plan.source_collection),
        target=target,
        close=milvus_client.close,
    )


def build_parser() -> argparse.ArgumentParser:
    """构造维护窗口迁移 CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="只读验证 PostgreSQL/Chroma 和预计导入量，不写 Milvus/checkpoint。",
    )
    mode.add_argument(
        "--rollback-check",
        action="store_true",
        help="只读验证 Chroma 原路径、stored-vector ANN 和 source fingerprint。",
    )
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--file-id", type=UUID)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--sample-top-k", type=int, default=5)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--maintenance-window-confirmed",
        action="store_true",
        help="确认 backend/frontend/worker 已停止写入且 active jobs 已 drain。",
    )
    parser.add_argument(
        "--backup-manifest",
        type=Path,
        help="真实导入必须提供已验证 PostgreSQL/uploads/Chroma 备份清单。",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    """在连接数据库前拒绝不安全或无界参数。"""
    if not 1 <= args.batch_size <= 1_000:
        raise MigrationValidationError("invalid_batch_size", "batch-size 必须在 1 到 1000")
    if args.sleep_seconds < 0 or args.sleep_seconds > 60:
        raise MigrationValidationError(
            "invalid_sleep_seconds",
            "sleep-seconds 必须在 0 到 60",
        )
    if not 1 <= args.sample_top_k <= 100:
        raise MigrationValidationError(
            "invalid_sample_top_k",
            "sample-top-k 必须在 1 到 100",
        )
    if not args.dry_run and not args.rollback_check:
        if not args.maintenance_window_confirmed:
            raise MigrationValidationError(
                "maintenance_window_not_confirmed",
                "真实导入前必须确认维护窗口并暂停写入",
            )
        if args.backup_manifest is None:
            raise MigrationValidationError(
                "backup_manifest_required",
                "真实导入前必须提供 backup manifest",
            )


def main(argv: Sequence[str] | None = None) -> int:
    """解析参数、执行迁移并只向 stdout 输出不含敏感数据的摘要。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        backup_evidence = (
            validate_backup_manifest(args.backup_manifest)
            if args.backup_manifest is not None
            else None
        )
        rows = list_vector_migration_chunk_rows(
            user_id=args.user_id,
            file_id=args.file_id,
        )
        if (
            not args.dry_run
            and not args.rollback_check
            and count_active_vector_index_jobs() != 0
        ):
            raise MigrationValidationError(
                "vector_jobs_not_drained",
                "仍有 queued/processing vector index jobs，不能开始导入",
            )
        plans = build_migration_file_plans(rows)
        if not plans:
            raise MigrationValidationError(
                "empty_migration_scope",
                "迁移范围内没有可对账的 PostgreSQL chunks",
            )
        report = run_migration(
            plans=plans,
            store_factory=_create_store_pair,
            options=MigrationOptions(
                dry_run=args.dry_run,
                rollback_check=args.rollback_check,
                batch_size=args.batch_size,
                sleep_seconds=args.sleep_seconds,
                sample_top_k=args.sample_top_k,
                checkpoint_path=args.checkpoint,
                report_path=args.report,
            ),
            backup_evidence=backup_evidence,
        )
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "code": exc.code if isinstance(exc, MigrationValidationError) else "unexpected_error",
            "message": sanitize_sensitive_text(str(exc))[:500],
        }, ensure_ascii=False))
        return 2

    summary = report["summary"]
    print(json.dumps({
        "ok": summary["files_failed"] == 0,
        "mode": report["mode"],
        "dry_run": report["dry_run"],
        "summary": summary,
        "report": str(args.report),
        "checkpoint": (
            None
            if args.dry_run or args.rollback_check
            else str(args.checkpoint)
        ),
    }, ensure_ascii=False))
    return 0 if summary["files_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
