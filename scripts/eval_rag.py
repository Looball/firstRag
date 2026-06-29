#!/usr/bin/env python3
"""运行 FirstRAG 真实后端链路的轻量 RAG 回归评测。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CASES_PATH = Path("docs/evals/rag_eval_cases.jsonl")
DEFAULT_REPORT_PATH = Path("docs/evals/latest_rag_eval_report.md")
DEFAULT_RUNS_DIR = Path("docs/evals/runs")
SUGGESTED_PERFORMANCE_THRESHOLDS = [
    {
        "name": "average_retrieval_settings_ms",
        "label": "平均 settings",
        "operator": "<=",
        "threshold": 1000.0,
        "unit": "ms",
    },
    {
        "name": "average_knowledge_profile_ms",
        "label": "平均 profile",
        "operator": "<=",
        "threshold": 1000.0,
        "unit": "ms",
    },
    {
        "name": "average_retrieve_documents_ms",
        "label": "平均 retrieve",
        "operator": "<=",
        "threshold": 5000.0,
        "unit": "ms",
    },
    {
        "name": "average_retrieval_total_ms",
        "label": "平均 hybrid",
        "operator": "<=",
        "threshold": 3000.0,
        "unit": "ms",
    },
    {
        "name": "average_rerank_ms",
        "label": "平均 rerank",
        "operator": "<=",
        "threshold": 3000.0,
        "unit": "ms",
    },
]


class EvalError(RuntimeError):
    """评测运行过程中出现的可理解错误。"""


@dataclass
class ChatResult:
    """单次聊天流式响应的聚合结果。"""

    answer: str
    sources: list[dict[str, Any]]
    retrieval: dict[str, Any]
    message_id: str | None
    elapsed_seconds: float


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Run FirstRAG RAG evaluation cases against a live backend.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("FIRSTRAG_EVAL_BASE_URL", "http://127.0.0.1:8000"),
        help="FastAPI backend origin, default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("FIRSTRAG_EVAL_USERNAME"),
        help="Login username. Can also use FIRSTRAG_EVAL_USERNAME.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("FIRSTRAG_EVAL_PASSWORD"),
        help="Login password. Can also use FIRSTRAG_EVAL_PASSWORD.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"JSONL cases path, default: {DEFAULT_CASES_PATH}",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Markdown report path, default: {DEFAULT_REPORT_PATH}",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=f"Timestamped JSON run history dir, default: {DEFAULT_RUNS_DIR}",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Only write latest markdown report, skip timestamped JSON history.",
    )
    parser.add_argument(
        "--knowledge-base-name",
        default=None,
        help="Override knowledge_base_name for every case.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="HTTP timeout seconds for each request, default: 180.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=parse_pass_rate,
        default=None,
        help="Minimum acceptable pass rate in [0, 1]. If omitted, every case must pass.",
    )
    parser.add_argument(
        "--min-average-sources",
        type=parse_non_negative_float,
        default=None,
        help="Minimum acceptable average source count.",
    )
    parser.add_argument(
        "--max-average-first-token-ms",
        type=parse_non_negative_float,
        default=None,
        help=(
            "Maximum acceptable average first-token wait in milliseconds. "
            "Falls back to pre_answer_total_ms when first_answer_token_ms is unavailable."
        ),
    )
    parser.add_argument(
        "--max-average-elapsed-seconds",
        type=parse_non_negative_float,
        default=None,
        help="Maximum acceptable average end-to-end case latency in seconds.",
    )
    return parser.parse_args()


def parse_non_negative_float(value: str) -> float:
    """解析非负浮点数命令行参数。"""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def parse_pass_rate(value: str) -> float:
    """解析 0 到 1 之间的通过率门槛。"""
    parsed = parse_non_negative_float(value)
    if parsed > 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def normalize_base_url(base_url: str) -> str:
    """规范化后端 origin，移除末尾斜杠。"""
    return base_url.rstrip("/")


def request_json(
    method: str,
    base_url: str,
    path: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """发送 JSON 请求并返回 JSON 响应。"""
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EvalError(
            f"{method} {path} failed: HTTP {exc.code} {detail}",
        ) from exc
    except URLError as exc:
        raise EvalError(f"{method} {path} failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvalError(f"{method} {path} returned non-JSON response") from exc


def login(base_url: str, username: str, password: str, timeout: int) -> str:
    """登录并返回 access token。"""
    data = request_json(
        "POST",
        base_url,
        "/login",
        payload={"username": username, "password": password},
        timeout=timeout,
    )
    token = data.get("access_token")
    if not token:
        raise EvalError("登录响应中没有 access_token")
    return str(token)


def load_cases(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 评测用例。"""
    if not path.exists():
        raise EvalError(f"评测用例文件不存在：{path}")

    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            case = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EvalError(f"{path}:{line_number} 不是合法 JSON") from exc
        cases.append(case)

    if not cases:
        raise EvalError(f"评测用例文件为空：{path}")
    return cases


def choose_knowledge_base(
    knowledge_bases: list[dict[str, Any]],
    preferred_name: str | None,
) -> dict[str, Any]:
    """按名称或默认标记选择知识库。"""
    if preferred_name:
        for knowledge_base in knowledge_bases:
            if knowledge_base.get("name") == preferred_name:
                return knowledge_base

    for knowledge_base in knowledge_bases:
        if knowledge_base.get("is_default"):
            return knowledge_base

    if knowledge_bases:
        return knowledge_bases[0]
    raise EvalError("当前账号没有可用知识库")


def create_conversation(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    case_id: str,
    timeout: int,
) -> str:
    """为单条 case 创建临时会话。"""
    title = f"RAG Eval {case_id} {datetime.now().strftime('%Y%m%d%H%M%S')}"
    data = request_json(
        "POST",
        base_url,
        f"/chat/knowledge-bases/{knowledge_base_id}/conversations",
        token=token,
        payload={"title": title},
        timeout=timeout,
    )
    conversation = data.get("conversation") or {}
    conversation_id = conversation.get("id")
    if not conversation_id:
        raise EvalError("创建会话响应中没有 conversation.id")
    return str(conversation_id)


def dispatch_sse_event(
    event_name: str | None,
    data_lines: list[str],
    result: dict[str, Any],
) -> None:
    """解析并聚合单个 SSE 事件。"""
    if not event_name or not data_lines:
        return

    payload_text = "\n".join(data_lines)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return

    if event_name == "retrieval":
        result["retrieval"] = payload
    elif event_name == "llm_usage":
        llm = payload.get("llm")
        if isinstance(llm, dict):
            retrieval = result.setdefault("retrieval", {})
            diagnostics = retrieval.setdefault("diagnostics", {})
            existing_llm = diagnostics.get("llm")
            if not isinstance(existing_llm, dict):
                existing_llm = {}
            diagnostics["llm"] = {**existing_llm, **llm}
    elif event_name == "sources":
        result["sources"] = payload.get("sources") or []
    elif event_name == "answer":
        result["answer_parts"].append(str(payload.get("content") or ""))
    elif event_name == "done":
        result["done"] = payload
        result["message_id"] = payload.get("message_id")
        if not result["sources"]:
            result["sources"] = payload.get("sources") or []
    elif event_name == "error":
        raise EvalError(str(payload.get("message") or "聊天流返回 error 事件"))


def stream_chat(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    conversation_id: str,
    question: str,
    timeout: int,
) -> ChatResult:
    """调用 /chat 并解析 text/event-stream 响应。"""
    payload = {
        "knowledge_base_id": knowledge_base_id,
        "conversation_id": conversation_id,
        "message": question,
    }
    req = Request(
        f"{base_url}/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    result: dict[str, Any] = {
        "answer_parts": [],
        "sources": [],
        "retrieval": {},
        "message_id": None,
        "done": {},
    }
    event_name: str | None = None
    data_lines: list[str] = []
    started_at = time.monotonic()

    try:
        with urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").rstrip("\n")
                if line.endswith("\r"):
                    line = line[:-1]
                if line == "":
                    dispatch_sse_event(event_name, data_lines, result)
                    event_name = None
                    data_lines = []
                    continue
                if line.startswith("event:"):
                    event_name = line.partition(":")[2].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.partition(":")[2].lstrip())

            dispatch_sse_event(event_name, data_lines, result)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EvalError(f"POST /chat failed: HTTP {exc.code} {detail}") from exc
    except URLError as exc:
        raise EvalError(f"POST /chat failed: {exc}") from exc

    done = result["done"] or {}
    answer = done.get("answer") or "".join(result["answer_parts"])
    return ChatResult(
        answer=str(answer),
        sources=result["sources"],
        retrieval=result["retrieval"],
        message_id=result["message_id"],
        elapsed_seconds=time.monotonic() - started_at,
    )


def source_file_names(sources: list[dict[str, Any]]) -> list[str]:
    """提取引用来源中的文件名。"""
    return [
        str(source.get("file_name") or "")
        for source in sources
        if source.get("file_name")
    ]


def source_matches_expected(file_name: str, expected_file: str) -> bool:
    """判断实际引用文件名是否命中期望文件名。"""
    return file_name == expected_file or expected_file in file_name


def evaluate_case(case: dict[str, Any], chat_result: ChatResult) -> dict[str, Any]:
    """根据 case 期望计算单条评测结果。"""
    answer = chat_result.answer
    sources = chat_result.sources
    retrieval = chat_result.retrieval
    source_names = source_file_names(sources)

    checks: list[dict[str, Any]] = []

    if "expect_retrieval" in case:
        actual_need = retrieval.get(
            "final_need_retrieval",
            retrieval.get("need_retrieval"),
        )
        checks.append({
            "name": "retrieval",
            "passed": bool(actual_need) is bool(case["expect_retrieval"]),
            "expected": case["expect_retrieval"],
            "actual": actual_need,
        })

    min_sources = int(case.get("min_sources", 0))
    checks.append({
        "name": "min_sources",
        "passed": len(sources) >= min_sources,
        "expected": min_sources,
        "actual": len(sources),
    })

    expected_files = case.get("expected_files") or []
    if expected_files:
        file_hit = any(
            source_matches_expected(file_name, expected_file)
            for file_name in source_names
            for expected_file in expected_files
        )
        checks.append({
            "name": "expected_files",
            "passed": file_hit,
            "expected": expected_files,
            "actual": source_names,
        })

    expected_keywords = case.get("expected_keywords") or []
    if expected_keywords:
        missing_keywords = [
            keyword
            for keyword in expected_keywords
            if str(keyword).lower() not in answer.lower()
        ]
        checks.append({
            "name": "expected_keywords",
            "passed": not missing_keywords,
            "expected": expected_keywords,
            "actual": {
                "missing": missing_keywords,
            },
        })

    expected_reason_keywords = case.get("expected_reason_keywords") or []
    if expected_reason_keywords:
        reason = str(retrieval.get("reason") or "")
        missing_reason_keywords = [
            keyword
            for keyword in expected_reason_keywords
            if str(keyword) not in reason
        ]
        checks.append({
            "name": "expected_reason_keywords",
            "passed": not missing_reason_keywords,
            "expected": expected_reason_keywords,
            "actual": {
                "reason": reason,
                "missing": missing_reason_keywords,
            },
        })

    expected_diagnostics = case.get("expected_diagnostics") or {}
    if isinstance(expected_diagnostics, dict):
        diagnostics = compact_diagnostics(retrieval)
        for path, expected_value in expected_diagnostics.items():
            actual_value = get_path_value(diagnostics, str(path))
            checks.append({
                "name": f"diagnostics.{path}",
                "passed": actual_value == expected_value,
                "expected": expected_value,
                "actual": actual_value,
            })

    return {
        "case": case,
        "chat_result": chat_result,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def format_bool(value: Any) -> str:
    """把布尔值格式化为中文展示。"""
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "—"


def numeric_value(value: Any) -> float | None:
    """把指标值规范化为可参与平均值计算的数字。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def average_or_none(values: list[float]) -> float | None:
    """计算平均值；没有样本时返回 None。"""
    if not values:
        return None
    return sum(values) / len(values)


def compact_diagnostics(retrieval: dict[str, Any]) -> dict[str, Any]:
    """提取报告中最常用的检索诊断字段。"""
    diagnostics = retrieval.get("diagnostics") or {}
    return {
        "need_retrieval": retrieval.get(
            "final_need_retrieval",
            retrieval.get("need_retrieval"),
        ),
        "retrieved_count": retrieval.get("retrieved_count"),
        "source_count": retrieval.get("source_count"),
        "retrieval_sources": retrieval.get("retrieval_sources")
        or diagnostics.get("retrieval_sources"),
        "vector_degraded": retrieval.get("vector_degraded")
        or diagnostics.get("vector_degraded"),
        "vector_count": diagnostics.get("vector_count"),
        "fulltext_count": diagnostics.get("fulltext_count"),
        "fused_count": diagnostics.get("fused_count"),
        "reranked_count": diagnostics.get("reranked_count"),
        "knowledge_profile_cache_hit": diagnostics.get(
            "knowledge_profile_cache_hit",
        ),
        "knowledge_profile_indexed_file_count": diagnostics.get(
            "knowledge_profile_indexed_file_count",
        ),
        "knowledge_profile_total_file_count": diagnostics.get(
            "knowledge_profile_total_file_count",
        ),
        "retrieval_settings_cache_hit": diagnostics.get(
            "retrieval_settings_cache_hit",
        ),
        "retrieval_settings_source": diagnostics.get(
            "retrieval_settings_source",
        ),
        "timing": diagnostics.get("timing") or {},
        "llm": diagnostics.get("llm") or {},
        "settings": diagnostics.get("settings") or {},
        "reason": retrieval.get("reason"),
    }


def get_path_value(value: dict[str, Any], path: str) -> Any:
    """按点分隔路径读取嵌套 dict 值。"""
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总本轮评测的核心指标。"""
    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    total_elapsed = sum(
        result["chat_result"].elapsed_seconds
        for result in results
    )
    total_sources = sum(
        len(result["chat_result"].sources)
        for result in results
    )
    retrieval_count = sum(
        1
        for result in results
        if compact_diagnostics(
            result["chat_result"].retrieval,
        )["need_retrieval"] is True
    )
    first_token_values: list[float] = []
    pre_answer_values: list[float] = []
    total_token_values: list[float] = []
    stage_values: dict[str, list[float]] = {
        "retrieval_settings_ms": [],
        "retrieval_settings_load_total_ms": [],
        "retrieval_settings_query_ms": [],
        "retrieval_settings_normalize_ms": [],
        "knowledge_profile_ms": [],
        "query_router_ms": [],
        "retrieve_documents_ms": [],
        "retrieval_total_ms": [],
        "rerank_ms": [],
    }
    cache_hit_count = 0
    cache_observed_count = 0
    settings_cache_hit_count = 0
    settings_cache_observed_count = 0
    for result in results:
        diagnostics = compact_diagnostics(result["chat_result"].retrieval)
        timing = diagnostics["timing"]
        first_token_ms = numeric_value(timing.get("first_answer_token_ms"))
        pre_answer_ms = numeric_value(timing.get("pre_answer_total_ms"))
        if pre_answer_ms is not None:
            pre_answer_values.append(pre_answer_ms)
        # eval 的流式 retrieval 事件有时早于 first_answer_token_ms，
        # 这种情况下用 pre_answer_total_ms 近似首 token 等待。
        effective_first_token_ms = (
            first_token_ms
            if first_token_ms is not None
            else pre_answer_ms
        )
        if effective_first_token_ms is not None:
            first_token_values.append(effective_first_token_ms)

        total_tokens = numeric_value(diagnostics["llm"].get("total_tokens"))
        if total_tokens is not None:
            total_token_values.append(total_tokens)

        for key, values in stage_values.items():
            stage_ms = numeric_value(timing.get(key))
            if stage_ms is not None:
                values.append(stage_ms)

        cache_hit = diagnostics.get("knowledge_profile_cache_hit")
        if isinstance(cache_hit, bool):
            cache_observed_count += 1
            if cache_hit:
                cache_hit_count += 1

        settings_cache_hit = diagnostics.get("retrieval_settings_cache_hit")
        if isinstance(settings_cache_hit, bool):
            settings_cache_observed_count += 1
            if settings_cache_hit:
                settings_cache_hit_count += 1

    return {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": passed_count / total if total else 0,
        "total_elapsed_seconds": total_elapsed,
        "average_elapsed_seconds": total_elapsed / total if total else 0,
        "average_sources": total_sources / total if total else 0,
        "retrieval_cases": retrieval_count,
        "average_first_token_ms": average_or_none(first_token_values),
        "average_pre_answer_ms": average_or_none(pre_answer_values),
        "average_retrieval_settings_ms": average_or_none(
            stage_values["retrieval_settings_ms"],
        ),
        "average_retrieval_settings_load_total_ms": average_or_none(
            stage_values["retrieval_settings_load_total_ms"],
        ),
        "average_retrieval_settings_query_ms": average_or_none(
            stage_values["retrieval_settings_query_ms"],
        ),
        "average_retrieval_settings_normalize_ms": average_or_none(
            stage_values["retrieval_settings_normalize_ms"],
        ),
        "average_knowledge_profile_ms": average_or_none(
            stage_values["knowledge_profile_ms"],
        ),
        "average_query_router_ms": average_or_none(
            stage_values["query_router_ms"],
        ),
        "average_retrieve_documents_ms": average_or_none(
            stage_values["retrieve_documents_ms"],
        ),
        "average_retrieval_total_ms": average_or_none(
            stage_values["retrieval_total_ms"],
        ),
        "average_rerank_ms": average_or_none(stage_values["rerank_ms"]),
        "knowledge_profile_cache_hit_count": cache_hit_count,
        "knowledge_profile_cache_observed_count": cache_observed_count,
        "knowledge_profile_cache_hit_rate": (
            cache_hit_count / cache_observed_count
            if cache_observed_count
            else None
        ),
        "retrieval_settings_cache_hit_count": settings_cache_hit_count,
        "retrieval_settings_cache_observed_count": (
            settings_cache_observed_count
        ),
        "retrieval_settings_cache_hit_rate": (
            settings_cache_hit_count / settings_cache_observed_count
            if settings_cache_observed_count
            else None
        ),
        "average_total_tokens": average_or_none(total_token_values),
    }


def build_quality_gate_checks(
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """根据命令行门槛生成质量门禁检查结果。"""
    checks: list[dict[str, Any]] = []

    if args.min_pass_rate is not None:
        current = numeric_value(summary.get("pass_rate"))
        checks.append({
            "name": "min_pass_rate",
            "label": "最低通过率",
            "operator": ">=",
            "threshold": args.min_pass_rate,
            "actual": current,
            "passed": current is not None and current >= args.min_pass_rate,
        })

    if args.min_average_sources is not None:
        current = numeric_value(summary.get("average_sources"))
        checks.append({
            "name": "min_average_sources",
            "label": "最低平均引用数",
            "operator": ">=",
            "threshold": args.min_average_sources,
            "actual": current,
            "passed": current is not None and current >= args.min_average_sources,
        })

    if args.max_average_first_token_ms is not None:
        current = numeric_value(summary.get("average_first_token_ms"))
        checks.append({
            "name": "max_average_first_token_ms",
            "label": "最高平均首 token 等待",
            "operator": "<=",
            "threshold": args.max_average_first_token_ms,
            "actual": current,
            "passed": (
                current is not None
                and current <= args.max_average_first_token_ms
            ),
        })

    if args.max_average_elapsed_seconds is not None:
        current = numeric_value(summary.get("average_elapsed_seconds"))
        checks.append({
            "name": "max_average_elapsed_seconds",
            "label": "最高平均总耗时",
            "operator": "<=",
            "threshold": args.max_average_elapsed_seconds,
            "actual": current,
            "passed": (
                current is not None
                and current <= args.max_average_elapsed_seconds
            ),
        })

    return checks


def build_suggested_performance_checks(
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """根据建议阈值生成性能观察项，不影响脚本退出码。"""
    checks: list[dict[str, Any]] = []
    for threshold in SUGGESTED_PERFORMANCE_THRESHOLDS:
        current = numeric_value(summary.get(threshold["name"]))
        checks.append({
            **threshold,
            "actual": current,
            "passed": current is None or current <= threshold["threshold"],
        })
    return checks


def serialize_source_summary(source: dict[str, Any]) -> dict[str, Any]:
    """序列化历史 JSON 中的引用摘要，避免写入过多正文。"""
    return {
        "file_id": source.get("file_id"),
        "file_name": source.get("file_name"),
        "chunk_index": source.get("chunk_index"),
        "retrieval_sources": source.get("retrieval_sources") or [],
        "vector_score": source.get("vector_score"),
        "fulltext_score": source.get("fulltext_score"),
        "rrf_score": source.get("rrf_score"),
        "rerank_score": source.get("rerank_score"),
    }


def serialize_result(result: dict[str, Any]) -> dict[str, Any]:
    """序列化单条评测结果用于历史 JSON。"""
    case = result["case"]
    chat_result = result["chat_result"]
    return {
        "id": case["id"],
        "question": case["question"],
        "passed": result["passed"],
        "elapsed_seconds": chat_result.elapsed_seconds,
        "message_id": chat_result.message_id,
        "answer_preview": chat_result.answer.replace("\n", " ")[:500],
        "checks": result["checks"],
        "diagnostics": compact_diagnostics(chat_result.retrieval),
        "sources": [
            serialize_source_summary(source)
            for source in chat_result.sources
        ],
    }


def build_run_record(
    results: list[dict[str, Any]],
    generated_at: datetime,
    base_url: str,
    cases_path: Path,
    quality_gate_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建可落盘的评测历史记录。"""
    quality_gate_checks = quality_gate_checks or []
    return {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "base_url": base_url,
        "cases_path": str(cases_path),
        "summary": build_summary(results),
        "quality_gate": {
            "passed": all(check["passed"] for check in quality_gate_checks),
            "checks": quality_gate_checks,
        },
        "performance_thresholds": build_suggested_performance_checks(
            build_summary(results),
        ),
        "cases": [
            serialize_result(result)
            for result in results
        ],
    }


def load_previous_run_record(runs_dir: Path) -> dict[str, Any] | None:
    """读取最近一次历史评测记录，用于本轮报告对比。"""
    if not runs_dir.exists():
        return None

    for run_path in sorted(runs_dir.glob("*.json"), reverse=True):
        try:
            return json.loads(run_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return None


def write_run_record(run_record: dict[str, Any], runs_dir: Path) -> Path:
    """写入带时间戳的 JSON 评测历史。"""
    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.fromisoformat(run_record["generated_at"])
    run_path = runs_dir / f"{generated_at.strftime('%Y%m%d_%H%M%S')}.json"
    run_path.write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run_path


def format_number(value: Any, precision: int = 2) -> str:
    """格式化报告中的数字。"""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return "—"


def format_delta(current: Any, previous: Any, precision: int = 2) -> str:
    """格式化本轮和上一轮指标差异。"""
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return "—"
    delta = current - previous
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.{precision}f}"


def append_history_comparison(
    lines: list[str],
    current_summary: dict[str, Any],
    previous_run: dict[str, Any] | None,
) -> None:
    """向 Markdown 报告追加历史对比区块。"""
    if previous_run is None:
        lines.extend([
            "- 历史对比：暂无上一轮记录",
            "",
        ])
        return

    previous_summary = previous_run.get("summary") or {}
    lines.extend([
        f"- 上一轮评测：{previous_run.get('generated_at', '未知时间')}",
        "",
        "## 与上次评测对比",
        "",
        "| 指标 | 本次 | 上次 | 变化 |",
        "| --- | ---: | ---: | ---: |",
    ])
    metric_names = {
        "passed": "通过数",
        "failed": "失败数",
        "pass_rate": "通过率",
        "average_elapsed_seconds": "平均耗时秒",
        "average_sources": "平均引用数",
        "average_first_token_ms": "平均首 token 毫秒",
        "average_pre_answer_ms": "平均回答前等待毫秒",
        "average_retrieval_settings_ms": "平均 settings 毫秒",
        "average_retrieval_settings_load_total_ms": "平均 settings load 毫秒",
        "average_retrieval_settings_query_ms": "平均 settings query 毫秒",
        "average_retrieval_settings_normalize_ms": "平均 settings normalize 毫秒",
        "average_knowledge_profile_ms": "平均 profile 毫秒",
        "average_query_router_ms": "平均 router 毫秒",
        "average_retrieve_documents_ms": "平均检索 Runnable 毫秒",
        "average_retrieval_total_ms": "平均混合检索毫秒",
        "average_rerank_ms": "平均 rerank 毫秒",
        "knowledge_profile_cache_hit_rate": "profile 缓存命中率",
        "retrieval_settings_cache_hit_rate": "settings 缓存命中率",
        "average_total_tokens": "平均 token",
        "retrieval_cases": "触发检索数",
    }
    for key, label in metric_names.items():
        precision = 2
        lines.append(
            "| {label} | {current} | {previous} | {delta} |".format(
                label=label,
                current=format_number(current_summary.get(key), precision),
                previous=format_number(previous_summary.get(key), precision),
                delta=format_delta(
                    current_summary.get(key),
                    previous_summary.get(key),
                    precision,
                ),
            ),
        )
    lines.append("")


def write_report(
    results: list[dict[str, Any]],
    report_path: Path,
    generated_at: datetime,
    previous_run: dict[str, Any] | None = None,
    history_path: Path | None = None,
    quality_gate_checks: list[dict[str, Any]] | None = None,
) -> None:
    """写入 Markdown 评测报告。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_summary(results)
    quality_gate_checks = quality_gate_checks or []
    quality_gate_passed = all(check["passed"] for check in quality_gate_checks)
    performance_checks = build_suggested_performance_checks(summary)
    lines = [
        "# RAG 评测报告",
        "",
        f"- 生成时间：{generated_at.isoformat(timespec='seconds')}",
        f"- 通过：{summary['passed']}/{summary['total']}",
        f"- 平均耗时：{summary['average_elapsed_seconds']:.2f}s",
        f"- 平均引用数：{summary['average_sources']:.2f}",
        f"- 平均首 token 等待：{format_number(summary['average_first_token_ms'])}ms",
        f"- 平均回答前等待：{format_number(summary['average_pre_answer_ms'])}ms",
        "- 平均阶段耗时：settings={settings}ms，profile={profile}ms，router={router}ms，检索={retrieve}ms，rerank={rerank}ms".format(
            settings=format_number(summary["average_retrieval_settings_ms"]),
            profile=format_number(summary["average_knowledge_profile_ms"]),
            router=format_number(summary["average_query_router_ms"]),
            retrieve=format_number(summary["average_retrieve_documents_ms"]),
            rerank=format_number(summary["average_rerank_ms"]),
        ),
        "- settings 子阶段：load={load}ms，query={query}ms，normalize={normalize}ms".format(
            load=format_number(
                summary["average_retrieval_settings_load_total_ms"],
            ),
            query=format_number(
                summary["average_retrieval_settings_query_ms"],
            ),
            normalize=format_number(
                summary["average_retrieval_settings_normalize_ms"],
            ),
        ),
        "- knowledge profile 缓存命中：{hits}/{observed}（{rate}）".format(
            hits=summary["knowledge_profile_cache_hit_count"],
            observed=summary["knowledge_profile_cache_observed_count"],
            rate=format_number(summary["knowledge_profile_cache_hit_rate"]),
        ),
        "- retrieval settings 缓存命中：{hits}/{observed}（{rate}）".format(
            hits=summary["retrieval_settings_cache_hit_count"],
            observed=summary["retrieval_settings_cache_observed_count"],
            rate=format_number(summary["retrieval_settings_cache_hit_rate"]),
        ),
        f"- 平均 token：{format_number(summary['average_total_tokens'])}",
        f"- 质量门禁：{'通过' if quality_gate_passed else '未通过'}",
        f"- 历史 JSON：{history_path or '未生成'}",
        "",
    ]
    append_history_comparison(lines, summary, previous_run)
    if quality_gate_checks:
        lines.extend([
            "## 质量门禁",
            "",
            "| 门槛 | 结果 | 当前 | 要求 |",
            "| --- | --- | ---: | ---: |",
        ])
        for check in quality_gate_checks:
            lines.append(
                "| {label} | {status} | {actual} | {operator} {threshold} |".format(
                    label=check["label"],
                    status="✅" if check["passed"] else "❌",
                    actual=format_number(check["actual"]),
                    operator=check["operator"],
                    threshold=format_number(check["threshold"]),
                ),
            )
        lines.append("")

    lines.extend([
        "## 性能门槛",
        "",
        "| 指标 | 结果 | 当前 | 建议阈值 |",
        "| --- | --- | ---: | ---: |",
    ])
    for check in performance_checks:
        current = format_number(check["actual"])
        threshold = format_number(check["threshold"])
        unit = check["unit"]
        lines.append(
            "| {label} | {status} | {current}{unit} | {operator} {threshold}{unit} |".format(
                label=check["label"],
                status="✅" if check["passed"] else "❌",
                current=current,
                unit=unit if current != "—" else "",
                operator=check["operator"],
                threshold=threshold,
            ),
        )
    lines.append("")

    lines.extend([
        "| Case | 结果 | 耗时 | 是否检索 | 引用数 | 命中文件 |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ])

    for result in results:
        case = result["case"]
        chat_result = result["chat_result"]
        retrieval = chat_result.retrieval
        diagnostics = compact_diagnostics(retrieval)
        file_names = source_file_names(chat_result.sources)
        lines.append(
            "| {case_id} | {status} | {elapsed:.2f}s | {need} | {source_count} | {files} |".format(
                case_id=case["id"],
                status="✅" if result["passed"] else "❌",
                elapsed=chat_result.elapsed_seconds,
                need=format_bool(diagnostics["need_retrieval"]),
                source_count=len(chat_result.sources),
                files="<br>".join(file_names) or "—",
            ),
        )

    lines.extend([
        "",
        "## 阶段耗时摘要",
        "",
        "| Case | pre-answer | settings | settings-load | settings-query | settings-normalize | profile | cache | router | retrieve | hybrid | rerank |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ])
    for result in results:
        case = result["case"]
        diagnostics = compact_diagnostics(result["chat_result"].retrieval)
        timing = diagnostics["timing"]
        lines.append(
            "| {case_id} | {pre_answer} | {settings} | {settings_load} | {settings_query} | {settings_normalize} | {profile} | {cache} | {router} | {retrieve} | {hybrid} | {rerank} |".format(
                case_id=case["id"],
                pre_answer=format_number(timing.get("pre_answer_total_ms")),
                settings=format_number(timing.get("retrieval_settings_ms")),
                settings_load=format_number(
                    timing.get("retrieval_settings_load_total_ms"),
                ),
                settings_query=format_number(
                    timing.get("retrieval_settings_query_ms"),
                ),
                settings_normalize=format_number(
                    timing.get("retrieval_settings_normalize_ms"),
                ),
                profile=format_number(timing.get("knowledge_profile_ms")),
                cache=format_bool(diagnostics["knowledge_profile_cache_hit"]),
                router=format_number(timing.get("query_router_ms")),
                retrieve=format_number(timing.get("retrieve_documents_ms")),
                hybrid=format_number(timing.get("retrieval_total_ms")),
                rerank=format_number(timing.get("rerank_ms")),
            ),
        )

    for result in results:
        case = result["case"]
        chat_result = result["chat_result"]
        diagnostics = compact_diagnostics(chat_result.retrieval)
        lines.extend([
            "",
            f"## {case['id']}",
            "",
            f"- 问题：{case['question']}",
            f"- 结果：{'通过' if result['passed'] else '未通过'}",
            f"- 耗时：{chat_result.elapsed_seconds:.2f}s",
            f"- 是否检索：{format_bool(diagnostics['need_retrieval'])}",
            f"- 召回片段：{diagnostics['retrieved_count']}",
            f"- 展示引用：{len(chat_result.sources)}",
            f"- 检索通道：{diagnostics['retrieval_sources'] or '—'}",
            f"- 向量降级：{format_bool(diagnostics['vector_degraded'])}",
            f"- 诊断计数：vector={diagnostics['vector_count']}，fulltext={diagnostics['fulltext_count']}，fused={diagnostics['fused_count']}，reranked={diagnostics['reranked_count']}",
            "- 知识库画像缓存：hit={hit}，indexed_files={indexed}，total_files={total}".format(
                hit=format_bool(diagnostics["knowledge_profile_cache_hit"]),
                indexed=diagnostics["knowledge_profile_indexed_file_count"] or "—",
                total=diagnostics["knowledge_profile_total_file_count"] or "—",
            ),
            "- 检索设置缓存：hit={hit}，source={source}".format(
                hit=format_bool(diagnostics["retrieval_settings_cache_hit"]),
                source=diagnostics["retrieval_settings_source"] or "—",
            ),
            "- 关键耗时：pre_answer={pre_answer}ms，settings={settings}ms，settings_load={settings_load}ms，settings_query={settings_query}ms，settings_normalize={settings_normalize}ms，profile={profile}ms，router={router}ms，retrieve={retrieve}ms，hybrid={retrieval}ms，rerank={rerank}ms".format(
                pre_answer=diagnostics["timing"].get("pre_answer_total_ms", "—"),
                settings=diagnostics["timing"].get("retrieval_settings_ms", "—"),
                settings_load=diagnostics["timing"].get(
                    "retrieval_settings_load_total_ms",
                    "—",
                ),
                settings_query=diagnostics["timing"].get(
                    "retrieval_settings_query_ms",
                    "—",
                ),
                settings_normalize=diagnostics["timing"].get(
                    "retrieval_settings_normalize_ms",
                    "—",
                ),
                profile=diagnostics["timing"].get("knowledge_profile_ms", "—"),
                router=diagnostics["timing"].get("query_router_ms", "—"),
                retrieve=diagnostics["timing"].get("retrieve_documents_ms", "—"),
                retrieval=diagnostics["timing"].get("retrieval_total_ms", "—"),
                rerank=diagnostics["timing"].get("rerank_ms", "—"),
            ),
            "- LLM：provider={provider}，model={model}，tokens={tokens}".format(
                provider=diagnostics["llm"].get("provider", "—"),
                model=diagnostics["llm"].get("model", "—"),
                tokens=diagnostics["llm"].get("total_tokens") or "—",
            ),
            f"- 判断原因：{diagnostics['reason'] or '—'}",
            "",
            "### 检查项",
            "",
            "| 检查 | 结果 | 期望 | 实际 |",
            "| --- | --- | --- | --- |",
        ])
        for check in result["checks"]:
            lines.append(
                "| {name} | {status} | `{expected}` | `{actual}` |".format(
                    name=check["name"],
                    status="✅" if check["passed"] else "❌",
                    expected=json.dumps(check["expected"], ensure_ascii=False),
                    actual=json.dumps(check["actual"], ensure_ascii=False),
                ),
            )

        lines.extend([
            "",
            "### 引用",
            "",
        ])
        if chat_result.sources:
            for index, source in enumerate(chat_result.sources, 1):
                lines.append(
                    "- {index}. {file_name} / chunk #{chunk_index} / sources={retrieval_sources} / rerank={rerank}".format(
                        index=index,
                        file_name=source.get("file_name") or "未知文件",
                        chunk_index=source.get("chunk_index", "—"),
                        retrieval_sources=source.get("retrieval_sources") or [],
                        rerank=source.get("rerank_score", "—"),
                    ),
                )
        else:
            lines.append("- 无")

        preview = chat_result.answer.replace("\n", " ")[:300]
        lines.extend([
            "",
            "### 答案预览",
            "",
            preview or "无",
        ])

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """命令行入口。"""
    args = parse_args()
    generated_at = datetime.now()
    if not args.username or not args.password:
        raise EvalError(
            "请通过 --username/--password 或 FIRSTRAG_EVAL_USERNAME/FIRSTRAG_EVAL_PASSWORD 提供登录信息",
        )

    base_url = normalize_base_url(args.base_url)
    token = login(base_url, args.username, args.password, args.timeout)
    cases = load_cases(args.cases)
    knowledge_base_data = request_json(
        "GET",
        base_url,
        "/chat/knowledge-bases",
        token=token,
        timeout=args.timeout,
    )
    knowledge_bases = knowledge_base_data.get("knowledge_bases") or []

    previous_run = None if args.no_history else load_previous_run_record(args.runs_dir)
    settings_cache: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for case in cases:
        preferred_name = args.knowledge_base_name or case.get("knowledge_base_name")
        knowledge_base = choose_knowledge_base(knowledge_bases, preferred_name)
        knowledge_base_id = str(knowledge_base["id"])

        original_settings = settings_cache.get(knowledge_base_id)
        if original_settings is None:
            settings_response = request_json(
                "GET",
                base_url,
                f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
                token=token,
                timeout=args.timeout,
            )
            original_settings = settings_response["settings"]
            settings_cache[knowledge_base_id] = original_settings

        case_settings = case.get("retrieval_settings") or {}
        if case_settings:
            request_json(
                "PATCH",
                base_url,
                f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
                token=token,
                payload=case_settings,
                timeout=args.timeout,
            )

        try:
            conversation_id = create_conversation(
                base_url,
                token,
                knowledge_base_id,
                str(case["id"]),
                args.timeout,
            )
            for pre_question in case.get("pre_questions") or []:
                stream_chat(
                    base_url,
                    token,
                    knowledge_base_id,
                    conversation_id,
                    str(pre_question),
                    args.timeout,
                )
            chat_result = stream_chat(
                base_url,
                token,
                knowledge_base_id,
                conversation_id,
                str(case["question"]),
                args.timeout,
            )
            results.append(evaluate_case(case, chat_result))
        finally:
            if case_settings:
                request_json(
                    "PATCH",
                    base_url,
                    f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
                    token=token,
                    payload=original_settings,
                    timeout=args.timeout,
                )

    summary = build_summary(results)
    quality_gate_checks = build_quality_gate_checks(summary, args)
    quality_gate_failed = [
        check
        for check in quality_gate_checks
        if not check["passed"]
    ]

    run_record = build_run_record(
        results=results,
        generated_at=generated_at,
        base_url=base_url,
        cases_path=args.cases,
        quality_gate_checks=quality_gate_checks,
    )
    history_path = None
    if not args.no_history:
        history_path = write_run_record(run_record, args.runs_dir)

    write_report(
        results=results,
        report_path=args.report,
        generated_at=generated_at,
        previous_run=previous_run,
        history_path=history_path,
        quality_gate_checks=quality_gate_checks,
    )
    passed_count = sum(1 for result in results if result["passed"])
    print(f"RAG eval passed {passed_count}/{len(results)}")
    if quality_gate_checks:
        print("Quality gate:")
        for check in quality_gate_checks:
            status = "PASS" if check["passed"] else "FAIL"
            actual = format_number(check["actual"])
            threshold = format_number(check["threshold"])
            print(
                f"- [{status}] {check['name']}: "
                f"{actual} {check['operator']} {threshold}",
            )
    print(f"Report: {args.report}")
    if history_path is not None:
        print(f"History: {history_path}")

    case_gate_passed = (
        True
        if args.min_pass_rate is not None
        else passed_count == len(results)
    )
    return 0 if case_gate_passed and not quality_gate_failed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvalError as exc:
        print(f"评测失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
