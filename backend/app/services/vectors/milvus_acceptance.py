"""验证已迁移 current vectors 的对账、隔离、Top-K 与 warmed ANN 延迟。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median
import time
from typing import Any, Sequence

from app.repositories.vector_migration_repository import (
    list_vector_migration_chunk_rows,
)
from app.services.vectors.chroma_to_milvus_migration import (
    MigrationValidationError,
    _create_store_pair,
    build_migration_file_plans,
    compare_top_k,
    validate_source_records,
    validate_target_records,
)


DEFAULT_REPORT_PATH = Path("/tmp/vector-migration/milvus-acceptance.json")
DEFAULT_ITERATIONS = 10
DEFAULT_TOP_K = 10
DEFAULT_WARMED_P95_MS = 50.0


def percentile(values: Sequence[float], percentile_value: float) -> float:
    """使用 nearest-rank 计算小样本 percentile。"""
    if not values:
        raise ValueError("percentile values 不能为空")
    if percentile_value <= 0 or percentile_value > 100:
        raise ValueError("percentile 必须位于 (0, 100]")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(len(ordered) * percentile_value / 100))
    return ordered[rank - 1]


def _safe_failure(code: str, message: str) -> dict[str, str]:
    """构造不包含正文、embedding 或凭据的失败记录。"""
    return {"code": code, "message": message}


def run_acceptance(
    *,
    iterations: int,
    top_k: int,
    warmed_p95_threshold_ms: float,
) -> dict[str, Any]:
    """对 PostgreSQL current scope 执行只读 Chroma/Milvus 对账和 ANN 门禁。"""
    if iterations < 10:
        raise ValueError("每个 collection 至少需要 10 次 ANN self-hit")
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0")
    if warmed_p95_threshold_ms <= 0:
        raise ValueError("warmed p95 threshold 必须大于 0")

    plans = build_migration_file_plans(list_vector_migration_chunk_rows())
    failures: list[dict[str, str]] = []
    collection_latencies: dict[str, list[float]] = defaultdict(list)
    benchmarked_collections: set[str] = set()
    file_count = 0
    entry_count = 0
    top_k_overlap_values: list[float] = []
    top1_matches = 0
    top1_samples = 0
    isolation_checks = 0
    self_hits = 0

    for plan in plans:
        pair = None
        try:
            pair = _create_store_pair(plan)
            source_records = pair.source.list_file_vectors(
                user_id=plan.user_id,
                file_id=plan.file_id,
                include_embeddings=True,
            )
            source = validate_source_records(plan, source_records)
            target_records = pair.target.list_file_vectors(
                user_id=plan.user_id,
                file_id=plan.file_id,
                include_embeddings=True,
            )
            validate_target_records(source, target_records)
            comparison = compare_top_k(
                plan=plan,
                source=source,
                source_store=pair.source,
                target_store=pair.target,
                k=top_k,
            )
            file_count += 1
            entry_count += len(target_records)
            top_k_overlap_values.append(float(comparison["mean_overlap"]))
            top1_matches += int(comparison["top1_matches"])
            top1_samples += int(comparison["sample_count"])

            if plan.target_collection not in benchmarked_collections:
                benchmarked_collections.add(str(plan.target_collection))
                sample = source.records[0]
                query_embedding = sample.embedding or []
                warmup_response = pair.target.search_vectors(
                    query_embedding=query_embedding,
                    user_id=plan.user_id,
                    file_ids=[plan.file_id],
                    k=1,
                )
                if warmup_response.issues or not warmup_response.results:
                    raise MigrationValidationError(
                        "milvus_ann_warmup_failed",
                        "Milvus filtered ANN warm-up 未返回健康候选",
                    )
                for _ in range(iterations):
                    started_at = time.perf_counter()
                    response = pair.target.search_vectors(
                        query_embedding=query_embedding,
                        user_id=plan.user_id,
                        file_ids=[plan.file_id],
                        k=1,
                    )
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    collection_latencies[str(plan.target_collection)].append(
                        elapsed_ms,
                    )
                    if response.issues or not response.results:
                        raise MigrationValidationError(
                            "milvus_ann_empty_or_degraded",
                            "Milvus filtered ANN 未返回健康候选",
                        )
                    actual = response.results[0].document
                    if (
                        actual.metadata.get("chunk_id") != sample.id
                        or actual.metadata.get("file_id") != plan.file_id
                    ):
                        raise MigrationValidationError(
                            "milvus_ann_self_hit_failed",
                            "Milvus stored-vector top-1 未命中自身",
                        )
                    self_hits += 1

                wrong_user = pair.target.search_vectors(
                    query_embedding=query_embedding,
                    user_id=plan.user_id + 1_000_000,
                    file_ids=[plan.file_id],
                    k=1,
                )
                wrong_file = pair.target.search_vectors(
                    query_embedding=query_embedding,
                    user_id=plan.user_id,
                    file_ids=["00000000-0000-0000-0000-000000000000"],
                    k=1,
                )
                if (
                    wrong_user.results
                    or wrong_user.issues
                    or wrong_file.results
                    or wrong_file.issues
                ):
                    raise MigrationValidationError(
                        "milvus_scope_isolation_failed",
                        "Milvus user/file scalar scope 返回了范围外候选或错误",
                    )
                isolation_checks += 2
        except MigrationValidationError as exc:
            failures.append(_safe_failure(exc.code, str(exc)))
        except Exception as exc:
            failures.append(_safe_failure(
                "unexpected_acceptance_error",
                f"{type(exc).__name__}: acceptance failed",
            ))
        finally:
            if pair is not None:
                pair.close()

    all_latencies = [
        value
        for values in collection_latencies.values()
        for value in values
    ]
    latency_summary = {
        "samples": len(all_latencies),
        "min_ms": round(min(all_latencies), 3) if all_latencies else None,
        "p50_ms": round(median(all_latencies), 3) if all_latencies else None,
        "p95_ms": round(percentile(all_latencies, 95), 3) if all_latencies else None,
        "max_ms": round(max(all_latencies), 3) if all_latencies else None,
        "threshold_ms": warmed_p95_threshold_ms,
    }
    p95_passed = bool(
        all_latencies
        and float(latency_summary["p95_ms"]) <= warmed_p95_threshold_ms
    )
    collection_count = len(benchmarked_collections)
    passed = bool(
        plans
        and not failures
        and file_count == len(plans)
        and entry_count == sum(len(plan.chunks) for plan in plans)
        and collection_count > 0
        and self_hits == collection_count * iterations
        and isolation_checks == collection_count * 2
        and top1_matches == top1_samples
        and all(value == 1.0 for value in top_k_overlap_values)
        and p95_passed
    )
    return {
        "schema_version": 1,
        "passed": passed,
        "scope": {
            "files": len(plans),
            "entries": sum(len(plan.chunks) for plan in plans),
            "collections": collection_count,
        },
        "verified": {
            "files": file_count,
            "entries": entry_count,
            "self_hits": self_hits,
            "expected_self_hits": collection_count * iterations,
            "isolation_checks": isolation_checks,
            "top1_matches": top1_matches,
            "top1_samples": top1_samples,
            "minimum_top_k_overlap": (
                min(top_k_overlap_values) if top_k_overlap_values else None
            ),
        },
        "warmed_filtered_ann": latency_summary,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    """构造只读 Milvus acceptance CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--warmed-p95-threshold-ms",
        type=float,
        default=DEFAULT_WARMED_P95_MS,
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行验收并写入不含敏感数据的 JSON 报告。"""
    args = build_parser().parse_args(argv)
    report = run_acceptance(
        iterations=args.iterations,
        top_k=args.top_k,
        warmed_p95_threshold_ms=args.warmed_p95_threshold_ms,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
