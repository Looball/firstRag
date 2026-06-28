#!/usr/bin/env python3
"""汇总 FirstRAG eval 历史记录，生成趋势摘要报告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RAG_RUNS_DIR = Path("docs/evals/runs")
DEFAULT_INDEXING_RUNS_DIR = Path("docs/evals/indexing_runs")
DEFAULT_REPORT_PATH = Path("docs/evals/latest_summary.md")


class EvalSummaryError(RuntimeError):
    """生成 eval 趋势摘要时出现的可理解错误。"""


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Build a markdown trend summary from FirstRAG eval history.",
    )
    parser.add_argument(
        "--rag-runs-dir",
        type=Path,
        default=DEFAULT_RAG_RUNS_DIR,
        help=f"RAG JSON history directory, default: {DEFAULT_RAG_RUNS_DIR}",
    )
    parser.add_argument(
        "--indexing-runs-dir",
        type=Path,
        default=DEFAULT_INDEXING_RUNS_DIR,
        help=(
            "Indexing JSON history directory, "
            f"default: {DEFAULT_INDEXING_RUNS_DIR}"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Markdown report path, default: {DEFAULT_REPORT_PATH}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum recent runs to include per section, default: 10.",
    )
    return parser.parse_args()


def parse_datetime(value: Any) -> datetime | None:
    """解析 ISO datetime，解析失败时返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_json_runs(directory: Path) -> list[dict[str, Any]]:
    """读取目录中的 JSON 历史记录，并按生成时间升序排列。"""
    if not directory.exists():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise EvalSummaryError(f"{path} 不是合法 JSON") from exc
        if isinstance(record, dict):
            record["_path"] = str(path)
            records.append(record)

    return sorted(
        records,
        key=lambda record: (
            parse_datetime(record.get("generated_at")) or datetime.min,
            record.get("_path", ""),
        ),
    )


def number_value(value: Any) -> float | None:
    """读取有限数字值。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def average(values: list[float]) -> float | None:
    """计算平均值，空列表返回 None。"""
    return sum(values) / len(values) if values else None


def format_number(value: Any, digits: int = 2, suffix: str = "") -> str:
    """格式化数字或空值。"""
    numeric = number_value(value)
    if numeric is None:
        return "-"
    return f"{numeric:.{digits}f}{suffix}"


def format_bool(value: Any) -> str:
    """格式化布尔值。"""
    if value is True:
        return "通过"
    if value is False:
        return "未通过"
    return "-"


def format_delta(current: Any, previous: Any, digits: int = 2) -> str:
    """格式化当前值相对前一次的变化。"""
    current_number = number_value(current)
    previous_number = number_value(previous)
    if current_number is None or previous_number is None:
        return "-"
    delta = current_number - previous_number
    if abs(delta) < 10 ** (-digits):
        return "0"
    return f"{delta:+.{digits}f}"


def latest(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """返回最近一条记录。"""
    return records[-1] if records else None


def summarize_rag(records: list[dict[str, Any]]) -> dict[str, Any]:
    """生成 RAG 历史摘要指标。"""
    summaries = [
        record.get("summary")
        for record in records
        if isinstance(record.get("summary"), dict)
    ]
    pass_rates = [
        value
        for summary in summaries
        if (value := number_value(summary.get("pass_rate"))) is not None
    ]
    average_elapsed = [
        value
        for summary in summaries
        if (
            value := number_value(summary.get("average_elapsed_seconds"))
        ) is not None
    ]
    average_first_token = [
        value
        for summary in summaries
        if (value := number_value(summary.get("average_first_token_ms")))
        is not None
    ]
    average_sources = [
        value
        for summary in summaries
        if (value := number_value(summary.get("average_sources"))) is not None
    ]

    return {
        "runs": len(records),
        "average_pass_rate": average(pass_rates),
        "average_elapsed_seconds": average(average_elapsed),
        "average_first_token_ms": average(average_first_token),
        "average_sources": average(average_sources),
        "latest": latest(records),
    }


def summarize_indexing(records: list[dict[str, Any]]) -> dict[str, Any]:
    """生成 indexing 历史摘要指标。"""
    passed_count = sum(1 for record in records if record.get("passed") is True)
    elapsed_values = [
        value
        for record in records
        if (
            value := number_value(
                (record.get("chat") or {}).get("elapsed_seconds")
                if isinstance(record.get("chat"), dict)
                else None
            )
        )
        is not None
    ]
    source_counts = [
        value
        for record in records
        if (
            value := number_value(
                ((record.get("chat") or {}).get("diagnostics") or {}).get(
                    "source_count"
                )
                if isinstance(record.get("chat"), dict)
                and isinstance((record.get("chat") or {}).get("diagnostics"), dict)
                else None
            )
        )
        is not None
    ]

    return {
        "runs": len(records),
        "passed": passed_count,
        "pass_rate": passed_count / len(records) if records else None,
        "average_chat_elapsed_seconds": average(elapsed_values),
        "average_sources": average(source_counts),
        "latest": latest(records),
    }


def rag_recent_rows(records: list[dict[str, Any]], limit: int) -> list[str]:
    """生成最近 RAG 运行表格行。"""
    rows: list[str] = []
    recent = records[-limit:]
    previous_by_index = [None, *recent[:-1]]
    for record, previous in zip(recent, previous_by_index, strict=False):
        summary = record.get("summary") or {}
        previous_summary = previous.get("summary") if previous else {}
        quality_gate = record.get("quality_gate") or {}
        rows.append(
            "| {time} | {passed}/{total} | {rate} | {sources} | {first_token} | "
            "{elapsed} | {tokens} | {gate} | {delta} |".format(
                time=record.get("generated_at", "-"),
                passed=summary.get("passed", "-"),
                total=summary.get("total", "-"),
                rate=format_number(summary.get("pass_rate"), 2),
                sources=format_number(summary.get("average_sources"), 2),
                first_token=format_number(
                    summary.get("average_first_token_ms"),
                    2,
                    "ms",
                ),
                elapsed=format_number(
                    summary.get("average_elapsed_seconds"),
                    2,
                    "s",
                ),
                tokens=format_number(summary.get("average_total_tokens"), 2),
                gate=format_bool(quality_gate.get("passed")),
                delta=format_delta(
                    summary.get("average_first_token_ms"),
                    previous_summary.get("average_first_token_ms")
                    if isinstance(previous_summary, dict)
                    else None,
                    2,
                ),
            )
        )
    return rows


def indexing_recent_rows(records: list[dict[str, Any]], limit: int) -> list[str]:
    """生成最近 indexing 运行表格行。"""
    rows: list[str] = []
    for record in records[-limit:]:
        chat = record.get("chat") if isinstance(record.get("chat"), dict) else {}
        diagnostics = (
            chat.get("diagnostics")
            if isinstance(chat.get("diagnostics"), dict)
            else {}
        )
        job = record.get("job") if isinstance(record.get("job"), dict) else {}
        rows.append(
            "| {time} | {passed} | {job_status} | {elapsed} | {sources} | "
            "{vector_degraded} | {cleanup} |".format(
                time=record.get("generated_at", "-"),
                passed=format_bool(record.get("passed")),
                job_status=job.get("status", "-"),
                elapsed=format_number(chat.get("elapsed_seconds"), 2, "s"),
                sources=format_number(diagnostics.get("source_count"), 0),
                vector_degraded=(
                    "是"
                    if diagnostics.get("vector_degraded") is True
                    else "否"
                    if diagnostics.get("vector_degraded") is False
                    else "-"
                ),
                cleanup="是" if record.get("cleanup_done") is True else "否",
            )
        )
    return rows


def build_report(
    rag_records: list[dict[str, Any]],
    indexing_records: list[dict[str, Any]],
    limit: int,
) -> str:
    """生成 Markdown 趋势摘要。"""
    rag_summary = summarize_rag(rag_records)
    indexing_summary = summarize_indexing(indexing_records)
    generated_at = datetime.now().replace(microsecond=0).isoformat()

    lines = [
        "# Eval 历史趋势摘要",
        "",
        f"- 生成时间：{generated_at}",
        f"- RAG 历史记录数：{rag_summary['runs']}",
        f"- Indexing 历史记录数：{indexing_summary['runs']}",
        "",
        "## RAG 总览",
        "",
        "| 指标 | 值 |",
        "| --- | ---: |",
        f"| 平均通过率 | {format_number(rag_summary['average_pass_rate'], 2)} |",
        f"| 平均耗时 | {format_number(rag_summary['average_elapsed_seconds'], 2, 's')} |",
        f"| 平均首 token | {format_number(rag_summary['average_first_token_ms'], 2, 'ms')} |",
        f"| 平均引用数 | {format_number(rag_summary['average_sources'], 2)} |",
        "",
        "## 最近 RAG 运行",
        "",
        "| 时间 | 通过 | 通过率 | 平均引用 | 平均首 token | 平均耗时 | 平均 token | 门禁 | 首 token 变化 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    lines.extend(rag_recent_rows(rag_records, limit) or ["| - | - | - | - | - | - | - | - | - |"])

    lines.extend([
        "",
        "## Indexing 总览",
        "",
        "| 指标 | 值 |",
        "| --- | ---: |",
        f"| 通过次数 | {indexing_summary['passed']}/{indexing_summary['runs']} |",
        f"| 通过率 | {format_number(indexing_summary['pass_rate'], 2)} |",
        f"| 平均聊天耗时 | {format_number(indexing_summary['average_chat_elapsed_seconds'], 2, 's')} |",
        f"| 平均引用数 | {format_number(indexing_summary['average_sources'], 2)} |",
        "",
        "## 最近 Indexing 运行",
        "",
        "| 时间 | 结果 | Job 状态 | 聊天耗时 | 引用数 | 向量降级 | 清理关联 |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ])
    lines.extend(
        indexing_recent_rows(indexing_records, limit)
        or ["| - | - | - | - | - | - | - |"]
    )

    lines.extend([
        "",
        "## 说明",
        "",
        "- 本报告只读取本地历史 JSON，不访问后端服务。",
        "- 报告不输出账号密码、令牌、密钥或数据库连接串。",
        "- `首 token 变化` 表示本轮 RAG 平均首 token 等待相对上一条展示记录的变化，单位毫秒。",
    ])
    return "\n".join(lines) + "\n"


def write_report(report_path: Path, content: str) -> None:
    """写入 Markdown 报告。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


def main() -> int:
    """脚本入口。"""
    args = parse_args()
    if args.limit <= 0:
        raise EvalSummaryError("--limit 必须大于 0")

    rag_records = load_json_runs(args.rag_runs_dir)
    indexing_records = load_json_runs(args.indexing_runs_dir)
    content = build_report(rag_records, indexing_records, args.limit)
    write_report(args.report, content)

    print(f"Eval summary written: {args.report}")
    print(f"RAG runs: {len(rag_records)}")
    print(f"Indexing runs: {len(indexing_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
