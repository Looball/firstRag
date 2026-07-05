#!/usr/bin/env python3
"""运行 FirstRAG 文件上传与向量化链路的真实回归验收。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_REPORT_PATH = Path("docs/evals/latest_indexing_eval_report.md")
DEFAULT_RUNS_DIR = Path("docs/evals/indexing_runs")
SUCCESS_JOB_STATUSES = {"completed", "succeeded"}
TERMINAL_JOB_STATUSES = {*SUCCESS_JOB_STATUSES, "failed", "cancelled"}
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f"
    b"\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class EvalError(RuntimeError):
    """上传与向量化验收过程中的可理解错误。"""


@dataclass
class ChatResult:
    """聊天流式响应聚合结果。"""

    answer: str
    sources: list[dict[str, Any]]
    retrieval: dict[str, Any]
    done: dict[str, Any]
    elapsed_seconds: float


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Run FirstRAG upload/indexing evaluation against a live backend.",
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
        "--knowledge-base-name",
        default=os.getenv("FIRSTRAG_EVAL_KNOWLEDGE_BASE_NAME"),
        help="Knowledge base name. Defaults to the account default knowledge base.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("FIRSTRAG_EVAL_TIMEOUT", "180")),
        help="HTTP timeout seconds for each request, default: 180.",
    )
    parser.add_argument(
        "--job-timeout",
        type=int,
        default=int(os.getenv("FIRSTRAG_INDEXING_EVAL_JOB_TIMEOUT", "240")),
        help="Seconds to wait for vector index job completion, default: 240.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("FIRSTRAG_INDEXING_EVAL_POLL_INTERVAL", "2")),
        help="Seconds between job status polls, default: 2.",
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
        "--keep-file",
        action="store_true",
        help="Keep the uploaded file associated with the knowledge base.",
    )
    parser.add_argument(
        "--file-kind",
        choices=("markdown", "image"),
        default=os.getenv("FIRSTRAG_INDEXING_EVAL_FILE_KIND", "markdown"),
        help=(
            "Temporary file kind. Use image to exercise PNG + vision parsing; "
            "default: markdown."
        ),
    )
    return parser.parse_args()


def normalize_base_url(base_url: str) -> str:
    """规范化后端 origin。"""
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


def request_multipart_upload(
    base_url: str,
    path: str,
    token: str,
    filename: str,
    content: str | bytes,
    content_type: str,
    timeout: int,
) -> dict[str, Any]:
    """用 multipart/form-data 上传单个临时文件。"""
    boundary = f"----FirstRAGIndexingEval{uuid.uuid4().hex}"
    file_content = content.encode("utf-8") if isinstance(content, str) else content
    body_parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="auto_index"\r\n\r\n'
            "true\r\n"
        ),
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="description"\r\n\r\n'
            "indexing eval temporary file\r\n"
        ),
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n",
        file_content,
        "\r\n",
        f"--{boundary}--\r\n",
    ]
    body = b"".join(
        part.encode("utf-8") if isinstance(part, str) else part
        for part in body_parts
    )
    req = Request(
        f"{base_url}{path}",
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EvalError(
            f"POST {path} failed: HTTP {exc.code} {detail}",
        ) from exc
    except URLError as exc:
        raise EvalError(f"POST {path} failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvalError(f"POST {path} returned non-JSON response") from exc


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
    run_id: str,
    timeout: int,
) -> str:
    """为 indexing eval 创建临时会话。"""
    title = f"Indexing Eval {run_id}"
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
    """发送聊天请求并聚合 SSE 响应。"""
    body = json.dumps({
        "conversation_id": conversation_id,
        "knowledge_base_id": knowledge_base_id,
        "message": question,
    }, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{base_url}/chat",
        data=body,
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    result: dict[str, Any] = {
        "answer_parts": [],
        "sources": [],
        "retrieval": {},
        "done": {},
    }
    started_at = time.monotonic()

    try:
        with urlopen(req, timeout=timeout) as resp:
            event_name: str | None = None
            data_lines: list[str] = []
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
                    event_name = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
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
        done=done,
        elapsed_seconds=time.monotonic() - started_at,
    )


def wait_for_job(
    base_url: str,
    token: str,
    job_id: str,
    timeout: int,
    poll_interval: float,
    request_timeout: int,
) -> dict[str, Any]:
    """轮询等待向量化任务进入终态。"""
    deadline = time.monotonic() + timeout
    last_job: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        data = request_json(
            "GET",
            base_url,
            f"/chat/vector-index-jobs/{job_id}",
            token=token,
            timeout=request_timeout,
        )
        last_job = data.get("job") or {}
        status = str(last_job.get("status") or "")
        if status in TERMINAL_JOB_STATUSES:
            if status not in SUCCESS_JOB_STATUSES:
                raise EvalError(
                    "向量化任务未成功完成："
                    f"status={status}, error={last_job.get('error_message')}",
                )
            return last_job
        time.sleep(poll_interval)

    raise EvalError(f"等待向量化任务超时，最后状态：{last_job}")


def find_file_in_knowledge_base(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    file_id: str,
    timeout: int,
) -> dict[str, Any] | None:
    """在知识库文件列表中查找指定文件。"""
    data = request_json(
        "GET",
        base_url,
        f"/chat/knowledge-base/{knowledge_base_id}/files",
        token=token,
        timeout=timeout,
    )
    for file_record in data.get("files") or []:
        if str(file_record.get("id")) == file_id:
            return file_record
    return None


def remove_file_relation(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    file_id: str,
    timeout: int,
) -> None:
    """解除临时文件与知识库关联。"""
    request_json(
        "DELETE",
        base_url,
        f"/chat/knowledge-base/{knowledge_base_id}/files/{file_id}",
        token=token,
        timeout=timeout,
    )


def build_temp_markdown_file(run_id: str) -> tuple[str, str, str, str]:
    """构建本轮评测专用的唯一 Markdown 文件名、正文和查询关键词。"""
    keyword = f"FirstRAGIndexingEval-{run_id}"
    filename = f"firstrag-indexing-eval-{run_id}.md"
    content = (
        f"# FirstRAG indexing eval {run_id}\n\n"
        f"唯一验收标识：{keyword}。\n\n"
        "这份临时文档用于验证 FirstRAG 的上传、向量化、全文检索、"
        "向量检索和聊天引用链路。若系统被问到本轮索引验收标识，"
        f"应当引用本文件并回答标识是 {keyword}。\n"
    )
    return filename, content, "text/markdown", keyword


def build_temp_image_file(run_id: str) -> tuple[str, bytes, str, str]:
    """构建本轮评测专用的最小 PNG 图片文件。"""
    keyword = f"FirstRAGImageIndexingEval-{run_id}"
    filename = f"firstrag-image-indexing-eval-{keyword}.png"
    return filename, MINIMAL_PNG_BYTES, "image/png", keyword


def build_temp_file(run_id: str, file_kind: str) -> tuple[str, str | bytes, str, str]:
    """按评测类型构建临时文件。"""
    if file_kind == "image":
        return build_temp_image_file(run_id)
    return build_temp_markdown_file(run_id)


def compact_diagnostics(retrieval: dict[str, Any]) -> dict[str, Any]:
    """提取报告需要展示的诊断字段。"""
    diagnostics = retrieval.get("diagnostics") or {}
    return {
        "need_retrieval": retrieval.get(
            "final_need_retrieval",
            retrieval.get("need_retrieval"),
        ),
        "retrieved_count": retrieval.get("retrieved_count"),
        "source_count": retrieval.get("source_count"),
        "retrieval_sources": (
            retrieval.get("retrieval_sources")
            or diagnostics.get("retrieval_sources")
        ),
        "vector_degraded": (
            retrieval.get("vector_degraded")
            or diagnostics.get("vector_degraded")
        ),
        "vector_errors": (
            retrieval.get("vector_errors")
            or diagnostics.get("vector_errors")
            or []
        ),
        "timing": diagnostics.get("timing") or {},
        "llm": diagnostics.get("llm") or {},
        "reason": retrieval.get("reason"),
    }


def evaluate_result(
    *,
    upload_response: dict[str, Any],
    file_record: dict[str, Any] | None,
    job: dict[str, Any],
    chat_result: ChatResult,
    expected_filename: str,
    expected_keyword: str,
) -> list[dict[str, Any]]:
    """生成本轮 indexing eval 检查项。"""
    source_names = [
        str(source.get("file_name") or "")
        for source in chat_result.sources
    ]
    uploaded_file_sources = [
        source
        for source in chat_result.sources
        if str(source.get("file_name") or "") == expected_filename
    ]
    uploaded_file_source_channels = [
        source.get("retrieval_sources") or []
        for source in uploaded_file_sources
    ]
    uploaded_file_has_vector_source = any(
        "vector" in channels
        for channels in uploaded_file_source_channels
    )
    answer = chat_result.answer
    diagnostics = compact_diagnostics(chat_result.retrieval)
    return [
        {
            "name": "upload_success",
            "passed": bool(upload_response.get("success")),
            "expected": True,
            "actual": upload_response.get("success"),
        },
        {
            "name": "file_visible_in_knowledge_base",
            "passed": file_record is not None,
            "expected": expected_filename,
            "actual": file_record.get("original_name") if file_record else None,
        },
        {
            "name": "job_completed",
            "passed": job.get("status") in SUCCESS_JOB_STATUSES,
            "expected": sorted(SUCCESS_JOB_STATUSES),
            "actual": job.get("status"),
        },
        {
            "name": "file_status_indexed",
            "passed": (file_record or {}).get("status") == "indexed",
            "expected": "indexed",
            "actual": (file_record or {}).get("status"),
        },
        {
            "name": "chat_retrieved",
            "passed": diagnostics["need_retrieval"] is True,
            "expected": True,
            "actual": diagnostics["need_retrieval"],
        },
        {
            "name": "source_contains_uploaded_file",
            "passed": expected_filename in source_names,
            "expected": expected_filename,
            "actual": source_names,
        },
        {
            "name": "chat_vector_not_degraded",
            "passed": diagnostics["vector_degraded"] is not True,
            "expected": False,
            "actual": {
                "vector_degraded": diagnostics["vector_degraded"],
                "vector_errors": diagnostics["vector_errors"],
            },
        },
        {
            "name": "uploaded_file_source_uses_vector",
            "passed": uploaded_file_has_vector_source,
            "expected": "vector",
            "actual": uploaded_file_source_channels,
        },
        {
            "name": "answer_contains_eval_keyword",
            "passed": expected_keyword.lower() in answer.lower(),
            "expected": expected_keyword,
            "actual": answer[:500],
        },
    ]


def serialize_run_record(
    *,
    generated_at: datetime,
    base_url: str,
    knowledge_base: dict[str, Any],
    filename: str,
    file_id: str,
    job: dict[str, Any],
    chat_result: ChatResult,
    checks: list[dict[str, Any]],
    cleanup_done: bool,
) -> dict[str, Any]:
    """构建历史 JSON 记录。"""
    diagnostics = compact_diagnostics(chat_result.retrieval)
    return {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "base_url": base_url,
        "knowledge_base": {
            "id": knowledge_base.get("id"),
            "name": knowledge_base.get("name"),
        },
        "file": {
            "id": file_id,
            "original_name": filename,
        },
        "job": {
            "id": job.get("id"),
            "status": job.get("status"),
            "error_message": job.get("error_message"),
            "chunk_count": job.get("chunk_count"),
        },
        "chat": {
            "elapsed_seconds": chat_result.elapsed_seconds,
            "answer_preview": chat_result.answer.replace("\n", " ")[:500],
            "diagnostics": diagnostics,
            "sources": [
                {
                    "file_id": source.get("file_id"),
                    "file_name": source.get("file_name"),
                    "chunk_index": source.get("chunk_index"),
                    "retrieval_sources": source.get("retrieval_sources") or [],
                    "rerank_score": source.get("rerank_score"),
                }
                for source in chat_result.sources
            ],
        },
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
        "cleanup_done": cleanup_done,
    }


def write_run_record(run_record: dict[str, Any], runs_dir: Path) -> Path:
    """写入带时间戳的历史 JSON。"""
    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.fromisoformat(run_record["generated_at"])
    run_path = runs_dir / f"{generated_at.strftime('%Y%m%d_%H%M%S')}.json"
    run_path.write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run_path


def write_report(
    report_path: Path,
    run_record: dict[str, Any],
    history_path: Path | None,
) -> None:
    """写入 Markdown 报告。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    chat = run_record["chat"]
    diagnostics = chat["diagnostics"]
    lines = [
        "# Indexing 评测报告",
        "",
        f"- 生成时间：{run_record['generated_at']}",
        f"- 结果：{'通过' if run_record['passed'] else '未通过'}",
        f"- 知识库：{run_record['knowledge_base']['name']}",
        f"- 文件：{run_record['file']['original_name']}",
        f"- 文件 ID：{run_record['file']['id']}",
        f"- Job：{run_record['job']['id']} / {run_record['job']['status']}",
        f"- 清理关联：{'是' if run_record['cleanup_done'] else '否'}",
        f"- 历史 JSON：{history_path or '未生成'}",
        "",
        "## 检查项",
        "",
        "| 检查 | 结果 | 期望 | 实际 |",
        "| --- | --- | --- | --- |",
    ]
    for check in run_record["checks"]:
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
        "## 聊天诊断",
        "",
        f"- 耗时：{chat['elapsed_seconds']:.2f}s",
        f"- 是否检索：{diagnostics['need_retrieval']}",
        f"- 召回片段：{diagnostics['retrieved_count']}",
        f"- 展示引用：{len(chat['sources'])}",
        f"- 检索通道：{diagnostics['retrieval_sources'] or '—'}",
        f"- 向量降级：{diagnostics['vector_degraded']}",
        f"- 向量错误：{diagnostics['vector_errors'] or '—'}",
        f"- LLM：provider={diagnostics['llm'].get('provider', '—')}，model={diagnostics['llm'].get('model', '—')}，tokens={diagnostics['llm'].get('total_tokens') or '—'}",
        f"- 判断原因：{diagnostics['reason'] or '—'}",
        "",
        "## 引用",
        "",
    ])
    if chat["sources"]:
        for index, source in enumerate(chat["sources"], 1):
            lines.append(
                "- {index}. {file_name} / chunk #{chunk_index} / sources={sources} / rerank={rerank}".format(
                    index=index,
                    file_name=source.get("file_name") or "未知文件",
                    chunk_index=source.get("chunk_index", "—"),
                    sources=source.get("retrieval_sources") or [],
                    rerank=source.get("rerank_score", "—"),
                ),
            )
    else:
        lines.append("- 无")

    lines.extend([
        "",
        "## 答案预览",
        "",
        chat["answer_preview"] or "无",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """命令行入口。"""
    args = parse_args()
    if not args.username or not args.password:
        raise EvalError(
            "请通过 --username/--password 或 FIRSTRAG_EVAL_USERNAME/FIRSTRAG_EVAL_PASSWORD 提供登录信息",
        )

    generated_at = datetime.now()
    run_id = generated_at.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    base_url = normalize_base_url(args.base_url)
    filename, file_content, content_type, keyword = build_temp_file(
        run_id,
        args.file_kind,
    )
    token = login(base_url, args.username, args.password, args.timeout)

    knowledge_base_data = request_json(
        "GET",
        base_url,
        "/chat/knowledge-bases",
        token=token,
        timeout=args.timeout,
    )
    knowledge_base = choose_knowledge_base(
        knowledge_base_data.get("knowledge_bases") or [],
        args.knowledge_base_name,
    )
    knowledge_base_id = str(knowledge_base["id"])

    uploaded_file_id: str | None = None
    cleanup_done = False
    try:
        upload_response = request_multipart_upload(
            base_url=base_url,
            path=f"/chat/knowledge-base/{knowledge_base_id}/files",
            token=token,
            filename=filename,
            content=file_content,
            content_type=content_type,
            timeout=args.timeout,
        )
        uploaded_files = upload_response.get("files") or []
        if not uploaded_files:
            raise EvalError("上传响应中没有 files")
        uploaded_file = uploaded_files[0]
        uploaded_file_id = str(uploaded_file.get("id") or "")
        if not uploaded_file_id:
            raise EvalError("上传响应中没有 file id")

        index_job = uploaded_file.get("index_job") or {}
        job_id = str(index_job.get("id") or "")
        if not job_id:
            raise EvalError("上传响应中没有自动向量化 job id")

        completed_job = wait_for_job(
            base_url=base_url,
            token=token,
            job_id=job_id,
            timeout=args.job_timeout,
            poll_interval=args.poll_interval,
            request_timeout=args.timeout,
        )
        file_record = find_file_in_knowledge_base(
            base_url=base_url,
            token=token,
            knowledge_base_id=knowledge_base_id,
            file_id=uploaded_file_id,
            timeout=args.timeout,
        )
        conversation_id = create_conversation(
            base_url=base_url,
            token=token,
            knowledge_base_id=knowledge_base_id,
            run_id=run_id,
            timeout=args.timeout,
        )
        question = f"本轮索引验收标识是什么？请引用包含 {keyword} 的文件回答。"
        chat_result = stream_chat(
            base_url=base_url,
            token=token,
            knowledge_base_id=knowledge_base_id,
            conversation_id=conversation_id,
            question=question,
            timeout=args.timeout,
        )
        checks = evaluate_result(
            upload_response=upload_response,
            file_record=file_record,
            job=completed_job,
            chat_result=chat_result,
            expected_filename=filename,
            expected_keyword=keyword,
        )
    finally:
        if uploaded_file_id and not args.keep_file:
            try:
                remove_file_relation(
                    base_url=base_url,
                    token=token,
                    knowledge_base_id=knowledge_base_id,
                    file_id=uploaded_file_id,
                    timeout=args.timeout,
                )
                cleanup_done = True
            except EvalError as exc:
                print(f"清理临时文件关联失败：{exc}", file=sys.stderr)

    run_record = serialize_run_record(
        generated_at=generated_at,
        base_url=base_url,
        knowledge_base=knowledge_base,
        filename=filename,
        file_id=uploaded_file_id or "",
        job=completed_job,
        chat_result=chat_result,
        checks=checks,
        cleanup_done=cleanup_done,
    )
    history_path = None
    if not args.no_history:
        history_path = write_run_record(run_record, args.runs_dir)
    write_report(args.report, run_record, history_path)

    print(f"Indexing eval {'passed' if run_record['passed'] else 'failed'}")
    print(f"File: {filename}")
    print(f"Job: {completed_job.get('id')} / {completed_job.get('status')}")
    print(f"Report: {args.report}")
    if history_path is not None:
        print(f"History: {history_path}")
    return 0 if run_record["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvalError as exc:
        print(f"评测失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
