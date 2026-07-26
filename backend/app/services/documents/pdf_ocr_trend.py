"""持久化 OCR benchmark 历史并生成同环境质量与耗时趋势。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any, Sequence


OCR_HISTORY_MAX_RECORDS = 50
OCR_TREND_WINDOW = 5
OCR_TREND_WATCH_TIME_RATIO = 1.25
OCR_TREND_REGRESSED_TIME_RATIO = 1.50
OCR_TREND_WATCH_QUALITY_DELTA = -0.01
OCR_TREND_REGRESSED_QUALITY_DELTA = -0.02
SUPPORTED_REPORT_SCHEMA_VERSIONS = {1, 2, 3}
_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


class OcrTrendError(ValueError):
    """OCR 历史或趋势参数无法安全处理时抛出。"""


def _number(value: object) -> float | None:
    """返回有限浮点数，布尔值、NaN 和无穷大均视为无效。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


def _parse_datetime(value: object) -> datetime | None:
    """解析 ISO 时间；无效值返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _datetime_sort_key(value: object) -> float:
    """把带或不带时区的 ISO 时间统一转换为 UTC timestamp。"""
    parsed = _parse_datetime(value)
    if parsed is None:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _safe_filename_part(value: object, fallback: str) -> str:
    """把受控运行标识转换为不含路径分隔符的文件名片段。"""
    normalized = _SAFE_FILENAME_PATTERN.sub("-", str(value or "").strip())
    return normalized.strip("-._")[:80] or fallback


def _markdown(value: object) -> str:
    """转义可能破坏 Markdown table 的运行时文本。"""
    return (
        str(value or "-")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("|", "\\|")
        .replace("`", "'")[:160]
    )


def _execution(record: dict[str, Any]) -> dict[str, Any]:
    """返回 v2 execution context，并兼容没有 execution 的 v1 报告。"""
    execution = record.get("execution")
    if isinstance(execution, dict):
        return execution
    return {
        "runner_os": "unknown",
        "runner_arch": "unknown",
        "run_id": "legacy",
        "run_attempt": "1",
        "commit_sha": "",
        "ref_name": "",
    }


def ocr_runtime_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    """返回只包含可比 OCR runtime 的稳定分组键。"""
    execution = _execution(record)
    return (
        str(execution.get("runner_os") or "unknown").casefold(),
        str(execution.get("runner_arch") or "unknown").casefold(),
        str(record.get("tesseract_version") or "unknown").casefold(),
        str(record.get("benchmark_suite") or "legacy").casefold(),
    )


def _record_identity(record: dict[str, Any]) -> tuple[str, str, str]:
    """返回可用于 CI rerun 去重的 runtime/run/attempt 标识。"""
    execution = _execution(record)
    run_id = str(execution.get("run_id") or "local")
    run_attempt = str(execution.get("run_attempt") or "1")
    if run_id == "local":
        run_id = str(record.get("generated_at") or "local")
    return ("/".join(ocr_runtime_key(record)), run_id, run_attempt)


def _validate_history_record(record: object) -> str | None:
    """返回历史记录不可用于趋势的安全原因；有效时返回 None。"""
    if not isinstance(record, dict):
        return "top level is not an object"
    if record.get("schema_version") not in SUPPORTED_REPORT_SCHEMA_VERSIONS:
        return "unsupported schema_version"
    if _parse_datetime(record.get("generated_at")) is None:
        return "generated_at is invalid"
    if not str(record.get("tesseract_version") or "").strip():
        return "tesseract_version is invalid"
    if (
        record.get("schema_version") == 3
        and not str(record.get("benchmark_suite") or "").strip()
    ):
        return "benchmark_suite is invalid"
    if _number(record.get("average_adaptive_similarity")) is None:
        return "average_adaptive_similarity is invalid"
    if _number(record.get("total_seconds")) is None:
        return "total_seconds is invalid"
    if not isinstance(record.get("passed"), bool):
        return "passed is invalid"
    cases = record.get("cases")
    if not isinstance(cases, list) or not cases:
        return "cases is invalid"
    for case in cases:
        if not isinstance(case, dict) or not str(case.get("case_id") or "").strip():
            return "case identity is invalid"
        if _number(case.get("adaptive_similarity")) is None:
            return "case adaptive_similarity is invalid"
        if _number(case.get("elapsed_seconds")) is None:
            return "case elapsed_seconds is invalid"
        if not isinstance(case.get("passed"), bool):
            return "case passed is invalid"
    return None


def _history_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """只保留趋势所需字段，拒绝把正文或任意扩展字段写入 cache。"""
    execution = _execution(payload)
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise OcrTrendError("当前 OCR report cases 无法持久化")
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "tesseract_version": payload["tesseract_version"],
        "benchmark_suite": str(payload.get("benchmark_suite") or "legacy")[:160],
        "execution": {
            key: str(execution.get(key) or "")[:160]
            for key in (
                "runner_os",
                "runner_arch",
                "run_id",
                "run_attempt",
                "commit_sha",
                "ref_name",
            )
        },
        "average_adaptive_similarity": payload["average_adaptive_similarity"],
        "total_seconds": payload["total_seconds"],
        "passed": payload["passed"],
        "cases": [
            {
                "case_id": str(case["case_id"])[:80],
                "adaptive_similarity": case["adaptive_similarity"],
                "elapsed_seconds": case["elapsed_seconds"],
                "selected_strategy": str(case.get("selected_strategy") or "")[:80],
                "passed": case["passed"],
            }
            for case in cases
        ],
    }


def load_ocr_history(
    history_directory: Path,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """加载、校验并按时间排序历史；损坏文件降级为 warning。"""
    if not history_directory.exists():
        return [], ()
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted(history_directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            warnings.append(f"ignored invalid history file: {path.name}")
            continue
        validation_error = _validate_history_record(payload)
        if validation_error is not None:
            warnings.append(
                f"ignored history file {path.name}: {validation_error}",
            )
            continue
        payload["_history_path"] = str(path)
        records.append(payload)

    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in sorted(
        records,
        key=lambda item: _datetime_sort_key(item.get("generated_at")),
    ):
        deduplicated[_record_identity(record)] = record
    return list(deduplicated.values()), tuple(warnings)


def persist_ocr_history_record(
    payload: dict[str, Any],
    history_directory: Path,
    *,
    max_records: int = OCR_HISTORY_MAX_RECORDS,
) -> Path:
    """写入当前报告，并把历史总量限制在安全上限内。"""
    if max_records < 2 or max_records > 500:
        raise OcrTrendError("OCR history max_records 必须位于 2 到 500 之间")
    validation_error = _validate_history_record(payload)
    if validation_error is not None:
        raise OcrTrendError(f"当前 OCR report 无法持久化：{validation_error}")
    persisted_payload = _history_payload(payload)
    history_directory.mkdir(parents=True, exist_ok=True)
    execution = _execution(persisted_payload)
    run_id = _safe_filename_part(execution.get("run_id"), "local")
    attempt = _safe_filename_part(execution.get("run_attempt"), "1")
    if run_id == "local":
        timestamp = _safe_filename_part(payload.get("generated_at"), "current")
        filename = f"local-{timestamp}.json"
    else:
        filename = f"ci-{run_id}-{attempt}.json"
    output_path = history_directory / filename
    output_path.write_text(
        json.dumps(persisted_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    records, _ = load_ocr_history(history_directory)
    if len(records) > max_records:
        ordered = sorted(
            records,
            key=lambda item: _datetime_sort_key(item.get("generated_at")),
        )
        removable = [
            record
            for record in ordered
            if record.get("_history_path") != str(output_path)
        ]
        for record in removable[: len(records) - max_records]:
            path_value = record.get("_history_path")
            if isinstance(path_value, str):
                Path(path_value).unlink(missing_ok=True)
    return output_path


def _median_metric(records: Sequence[dict[str, Any]], key: str) -> float | None:
    """返回记录指定有限数值字段的中位数。"""
    values = [
        value
        for record in records
        if (value := _number(record.get(key))) is not None
    ]
    return float(median(values)) if values else None


def assess_ocr_trend(
    comparable_records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """按最近同环境中位数评估当前质量与耗时趋势。"""
    if not comparable_records:
        raise OcrTrendError("OCR trend 至少需要一条当前记录")
    latest = comparable_records[-1]
    previous = list(comparable_records[:-1])[-OCR_TREND_WINDOW:]
    latest_quality = _number(latest.get("average_adaptive_similarity"))
    latest_seconds = _number(latest.get("total_seconds"))
    baseline_quality = _median_metric(
        previous,
        "average_adaptive_similarity",
    )
    baseline_seconds = _median_metric(previous, "total_seconds")
    quality_delta = (
        latest_quality - baseline_quality
        if latest_quality is not None and baseline_quality is not None
        else None
    )
    time_ratio = (
        latest_seconds / baseline_seconds
        if latest_seconds is not None
        and baseline_seconds is not None
        and baseline_seconds > 0
        else None
    )
    reasons: list[str] = []
    if latest.get("passed") is not True:
        status = "regressed"
        reasons.append("current OCR hard gate failed")
    elif not previous:
        status = "baseline"
        reasons.append("no comparable previous run")
    elif (
        quality_delta is not None
        and quality_delta < OCR_TREND_REGRESSED_QUALITY_DELTA
    ) or (
        time_ratio is not None
        and time_ratio >= OCR_TREND_REGRESSED_TIME_RATIO
    ):
        status = "regressed"
    elif (
        quality_delta is not None
        and quality_delta < OCR_TREND_WATCH_QUALITY_DELTA
    ) or (
        time_ratio is not None
        and time_ratio >= OCR_TREND_WATCH_TIME_RATIO
    ):
        status = "watch"
    else:
        status = "stable"
    if status in {"watch", "regressed"}:
        if quality_delta is not None and quality_delta < 0:
            reasons.append(f"quality delta {quality_delta:+.4f}")
        if time_ratio is not None and time_ratio >= OCR_TREND_WATCH_TIME_RATIO:
            reasons.append(f"time ratio {time_ratio:.2f}x")
    return {
        "status": status,
        "comparable_runs": len(comparable_records),
        "baseline_runs": len(previous),
        "baseline_quality": baseline_quality,
        "baseline_seconds": baseline_seconds,
        "quality_delta": quality_delta,
        "time_ratio": time_ratio,
        "reasons": tuple(reasons),
    }


def _format_number(value: object, digits: int = 3, suffix: str = "") -> str:
    """格式化趋势数值；缺失时返回短横线。"""
    normalized = _number(value)
    return "-" if normalized is None else f"{normalized:.{digits}f}{suffix}"


def _format_delta(value: object, digits: int = 3, suffix: str = "") -> str:
    """格式化带符号趋势变化。"""
    normalized = _number(value)
    return "-" if normalized is None else f"{normalized:+.{digits}f}{suffix}"


def _case_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """按 case id 返回合法 case 指标。"""
    cases = record.get("cases")
    if not isinstance(cases, list):
        return {}
    return {
        str(case.get("case_id")): case
        for case in cases
        if isinstance(case, dict) and case.get("case_id")
    }


def render_ocr_trend_markdown(
    records: Sequence[dict[str, Any]],
    warnings: Sequence[str] = (),
    *,
    limit: int = 10,
    current_record: dict[str, Any] | None = None,
) -> str:
    """生成同环境 OCR 质量和耗时趋势 Markdown。"""
    if limit < 1 or limit > 50:
        raise OcrTrendError("OCR trend limit 必须位于 1 到 50 之间")
    if not records:
        raise OcrTrendError("没有可用于 OCR trend 的历史记录")
    ordered = sorted(
        records,
        key=lambda item: _datetime_sort_key(item.get("generated_at")),
    )
    latest = current_record or ordered[-1]
    runtime_key = ocr_runtime_key(latest)
    latest_identity = _record_identity(latest)
    latest_timestamp = _datetime_sort_key(latest.get("generated_at"))
    comparable = [
        record
        for record in ordered
        if ocr_runtime_key(record) == runtime_key
        and _record_identity(record) != latest_identity
        and _datetime_sort_key(record.get("generated_at")) <= latest_timestamp
    ]
    comparable.append(latest)
    assessment = assess_ocr_trend(comparable)
    execution = _execution(latest)
    reasons = ", ".join(assessment["reasons"]) or "none"
    lines = [
        "# PDF OCR Historical Trend",
        "",
        f"- Trend status: **{assessment['status'].upper()}**",
        f"- Runtime: `{_markdown(execution.get('runner_os'))} / "
        f"{_markdown(execution.get('runner_arch'))} / "
        f"{_markdown(latest.get('tesseract_version'))}`",
        f"- Benchmark suite: `{_markdown(latest.get('benchmark_suite') or 'legacy')}`",
        f"- Comparable runs: `{assessment['comparable_runs']}`; "
        f"baseline window: `{assessment['baseline_runs']}`",
        f"- Latest quality: `{_format_number(latest.get('average_adaptive_similarity'), 4)}`; "
        f"baseline median: `{_format_number(assessment['baseline_quality'], 4)}`; "
        f"delta: `{_format_delta(assessment['quality_delta'], 4)}`",
        f"- Latest total time: `{_format_number(latest.get('total_seconds'), 3, 's')}`; "
        f"baseline median: `{_format_number(assessment['baseline_seconds'], 3, 's')}`; "
        f"ratio: `{_format_number(assessment['time_ratio'], 2, 'x')}`",
        f"- Reasons: `{_markdown(reasons)}`",
        "",
        "## Recent comparable runs",
        "",
        "| Generated | Run | Commit | Quality | Total | Change | Gate |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    recent = comparable[-limit:]
    previous_seconds: float | None = None
    for record in recent:
        record_execution = _execution(record)
        seconds = _number(record.get("total_seconds"))
        change = (
            (seconds / previous_seconds - 1) * 100
            if seconds is not None and previous_seconds is not None and previous_seconds > 0
            else None
        )
        commit_sha = str(record_execution.get("commit_sha") or "")[:12] or "-"
        run_label = (
            f"{record_execution.get('run_id', 'local')}/"
            f"{record_execution.get('run_attempt', '1')}"
        )
        lines.append(
            f"| {_markdown(record.get('generated_at'))} | `{_markdown(run_label)}` | "
            f"`{_markdown(commit_sha)}` | "
            f"{_format_number(record.get('average_adaptive_similarity'), 4)} | "
            f"{_format_number(seconds, 3, 's')} | "
            f"{_format_delta(change, 1, '%')} | "
            f"{'PASS' if record.get('passed') is True else 'FAIL'} |",
        )
        previous_seconds = seconds

    lines.extend([
        "",
        "## Latest case metrics",
        "",
        "| Case | Similarity | Baseline median | Time | Baseline median | Strategy |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ])
    latest_cases = _case_map(latest)
    baseline_case_maps = [_case_map(record) for record in comparable[:-1][-OCR_TREND_WINDOW:]]
    for case_id, case in sorted(latest_cases.items()):
        baseline_cases = [mapping[case_id] for mapping in baseline_case_maps if case_id in mapping]
        similarity_median = _median_metric(
            baseline_cases,
            "adaptive_similarity",
        )
        seconds_median = _median_metric(baseline_cases, "elapsed_seconds")
        lines.append(
            f"| `{_markdown(case_id)}` | "
            f"{_format_number(case.get('adaptive_similarity'), 4)} | "
            f"{_format_number(similarity_median, 4)} | "
            f"{_format_number(case.get('elapsed_seconds'), 3, 's')} | "
            f"{_format_number(seconds_median, 3, 's')} | "
            f"`{_markdown(case.get('selected_strategy'))}` |",
        )
    if warnings:
        lines.extend(["", "## History warnings", ""])
        lines.extend(f"- {_markdown(warning)}" for warning in warnings)
    lines.extend([
        "",
        "> Trend status is observational. The current OCR hard gate remains the CI blocker.",
    ])
    return "\n".join(lines) + "\n"


def update_ocr_history_and_trend(
    payload: dict[str, Any],
    history_directory: Path,
    trend_report_path: Path,
    *,
    max_records: int = OCR_HISTORY_MAX_RECORDS,
    limit: int = 10,
) -> tuple[Path, tuple[str, ...]]:
    """持久化当前报告、加载有界历史并写入趋势摘要。"""
    history_path = persist_ocr_history_record(
        payload,
        history_directory,
        max_records=max_records,
    )
    records, warnings = load_ocr_history(history_directory)
    current_record = next(
        (
            record
            for record in records
            if record.get("_history_path") == str(history_path)
        ),
        None,
    )
    if current_record is None:
        raise OcrTrendError("当前 OCR history record 写入后无法重新加载")
    trend_report_path.parent.mkdir(parents=True, exist_ok=True)
    trend_report_path.write_text(
        render_ocr_trend_markdown(
            records,
            warnings,
            limit=limit,
            current_record=current_record,
        ),
        encoding="utf-8",
    )
    return history_path, warnings
