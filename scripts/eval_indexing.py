#!/usr/bin/env python3
"""运行 FirstRAG 文件上传与向量化链路的真实回归验收。"""

from __future__ import annotations

import argparse
from io import BytesIO
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

import pymupdf
from PIL import Image, ImageChops, ImageStat


DEFAULT_REPORT_PATH = Path("docs/evals/latest_indexing_eval_report.md")
DEFAULT_RUNS_DIR = Path("docs/evals/indexing_runs")
SUCCESS_JOB_STATUSES = {"completed", "succeeded"}
TERMINAL_JOB_STATUSES = {*SUCCESS_JOB_STATUSES, "failed", "cancelled"}
INDEXING_EVAL_RETRIEVAL_SETTINGS = {
    "retrieval_mode": "always",
    "enable_query_router": False,
    "enable_rerank": False,
    "top_k": 20,
    "vector_top_k": 100,
    "sparse_top_k": 100,
    "rrf_k": 60,
}
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f"
    b"\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
MIXED_PDF_FILE_KIND = "mixed-pdf"
MIXED_PDF_SCANNED_PAGE_NUMBER = 2


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


@dataclass
class PdfPagePreviewEvidence:
    """记录 PNG 页预览的响应属性和三页图像比对结果。"""

    content_type: str
    cache_control: str
    content_disposition: str
    width: int
    height: int
    closest_page_number: int
    page_mean_differences: dict[int, float]


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
        "--exercise-vector-lifecycle",
        action="store_true",
        help=(
            "After the first successful retrieval, delete vectors, verify the "
            "empty state, reindex the same file, and verify vector retrieval again."
        ),
    )
    parser.add_argument(
        "--permanent-delete",
        action="store_true",
        help=(
            "Permanently delete the temporary file and verify its vector count is zero. "
            "Intended for isolated acceptance environments only."
        ),
    )
    parser.add_argument(
        "--file-kind",
        choices=("markdown", "image", MIXED_PDF_FILE_KIND),
        default=os.getenv("FIRSTRAG_INDEXING_EVAL_FILE_KIND", "markdown"),
        help=(
            "Temporary file kind. Use image for vision parsing or mixed-pdf "
            "for native text + OCR page and source-location checks; "
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


def request_binary(
    method: str,
    base_url: str,
    path: str,
    token: str | None = None,
    timeout: int = 180,
) -> tuple[bytes, dict[str, str]]:
    """发送二进制请求，并返回响应体与小写响应头。"""
    headers = {"Accept": "image/png"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(
        f"{base_url}{path}",
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read(), {
                key.lower(): value
                for key, value in resp.headers.items()
            }
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EvalError(
            f"{method} {path} failed: HTTP {exc.code} {detail}",
        ) from exc
    except URLError as exc:
        raise EvalError(f"{method} {path} failed: {exc}") from exc


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


def permanently_delete_file(
    base_url: str,
    token: str,
    file_id: str,
    timeout: int,
) -> None:
    """通过公开 API 永久删除验收临时文件。"""
    request_json(
        "DELETE",
        base_url,
        f"/chat/knowledge-files/{file_id}",
        token=token,
        timeout=timeout,
    )


def build_eval_vector_store(username: str) -> tuple[int, Any]:
    """在后端运行环境中创建当前用户的生产 vector store adapter。"""
    try:
        from app.repositories.auth_repository import get_user_by_username
        from app.services.vectors.vector_store_factory import get_vector_store
    except ImportError as exc:
        raise EvalError(
            "vector lifecycle 验收必须在可导入 backend app 的环境中运行",
        ) from exc

    user = get_user_by_username(username)
    if user is None:
        raise EvalError("vector lifecycle 验收用户不存在")
    user_id = int(user["id"])
    return user_id, get_vector_store(user_id)


def count_eval_file_vectors(
    vector_store: Any,
    *,
    user_id: int,
    file_id: str,
) -> int:
    """通过 provider-neutral adapter 统计目标文件向量，不读取正文或向量值。"""
    return int(vector_store.count_vectors(user_id=user_id, file_id=file_id))


def get_retrieval_settings(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    timeout: int,
) -> dict[str, Any]:
    """读取知识库当前检索设置。"""
    data = request_json(
        "GET",
        base_url,
        f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
        token=token,
        timeout=timeout,
    )
    return dict(data.get("settings") or {})


def update_retrieval_settings(
    base_url: str,
    token: str,
    knowledge_base_id: str,
    settings: dict[str, Any],
    timeout: int,
) -> None:
    """更新知识库检索设置。"""
    request_json(
        "PATCH",
        base_url,
        f"/chat/knowledge-base/{knowledge_base_id}/retrieval-settings",
        token=token,
        payload=settings,
        timeout=timeout,
    )


def get_source_chunk_context(
    base_url: str,
    token: str,
    file_id: str,
    chunk_index: int,
    timeout: int,
) -> dict[str, Any]:
    """读取引用目标及前后三个 chunk，验证页码与解析方式。"""
    return request_json(
        "GET",
        base_url,
        f"/chat/knowledge-files/{file_id}/chunks/{chunk_index}?radius=3",
        token=token,
        timeout=timeout,
    )


def inspect_pdf_page_preview(
    *,
    preview_content: bytes,
    response_headers: dict[str, str],
    pdf_content: bytes,
) -> PdfPagePreviewEvidence:
    """将预览 PNG 与原 PDF 各页渲染结果比较，确认返回的真实页码。"""
    try:
        with Image.open(BytesIO(preview_content)) as preview_source:
            if preview_source.format != "PNG":
                raise EvalError(
                    f"PDF 页面预览不是 PNG：format={preview_source.format}",
                )
            preview = preview_source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise EvalError("PDF 页面预览无法解析为有效 PNG") from exc

    page_differences: dict[int, float] = {}
    document = pymupdf.open(stream=pdf_content, filetype="pdf")
    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            max_edge = max(page.rect.width, page.rect.height)
            scale = min(2.0, 1800 / max_edge) if max_edge > 0 else 1.0
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            with Image.open(BytesIO(pixmap.tobytes("png"))) as reference_source:
                reference = reference_source.convert("RGB")
                if reference.size != preview.size:
                    reference = reference.resize(
                        preview.size,
                        Image.Resampling.LANCZOS,
                    )
                channel_means = ImageStat.Stat(
                    ImageChops.difference(preview, reference),
                ).mean
                page_differences[page_index + 1] = round(
                    sum(channel_means) / len(channel_means) / 255,
                    6,
                )
    finally:
        document.close()

    if not page_differences:
        raise EvalError("原 PDF 没有可用于预览比对的页面")
    closest_page_number = min(page_differences, key=page_differences.__getitem__)
    return PdfPagePreviewEvidence(
        content_type=response_headers.get("content-type", ""),
        cache_control=response_headers.get("cache-control", ""),
        content_disposition=response_headers.get("content-disposition", ""),
        width=preview.width,
        height=preview.height,
        closest_page_number=closest_page_number,
        page_mean_differences=page_differences,
    )


def build_temp_markdown_file(run_id: str) -> tuple[str, str, str, str]:
    """构建本轮评测专用的唯一 Markdown 文件名、正文和查询关键词。"""
    keyword = f"FirstRAGIndexingEval-{run_id}"
    filename = f"firstrag-indexing-eval-{run_id}.md"
    content = (
        f"# FirstRAG indexing eval {run_id}\n\n"
        f"唯一验收标识：{keyword}。\n\n"
        "这份临时文档用于验证 FirstRAG 的上传、Milvus dense/sparse hybrid "
        "检索和聊天引用链路。若系统被问到本轮索引验收标识，"
        f"应当引用本文件并回答标识是 {keyword}。\n"
    )
    return filename, content, "text/markdown", keyword


def build_temp_image_file(run_id: str) -> tuple[str, bytes, str, str]:
    """构建本轮评测专用的最小 PNG 图片文件。"""
    keyword = f"FirstRAGImageIndexingEval-{run_id}"
    filename = f"firstrag-image-indexing-eval-{keyword}.png"
    return filename, MINIMAL_PNG_BYTES, "image/png", keyword


def build_mixed_pdf_keywords(run_id: str) -> tuple[str, str, str]:
    """返回三页 PDF 的 native、scan、native 唯一标识。"""
    short_code = run_id.rsplit("-", maxsplit=1)[-1].upper()
    return (
        f"T083 NATIVE START {short_code}",
        f"T083 SCAN CODE {short_code}",
        f"T083 NATIVE END {short_code}",
    )


def _insert_pdf_text_lines(
    page: pymupdf.Page,
    title: str,
    lines: tuple[str, ...],
) -> None:
    """以安全页边距绘制清晰的验收页标题和正文。"""
    page.insert_text(
        (54, 86),
        title,
        fontname="helv",
        fontsize=22,
        color=(0.05, 0.13, 0.18),
    )
    for line_index, line in enumerate(lines):
        page.insert_text(
            (54, 150 + line_index * 48),
            line,
            fontname="helv",
            fontsize=22 if line_index == 0 else 18,
            color=(0, 0, 0),
        )
    page.draw_line(
        (54, 108),
        (541, 108),
        color=(0.16, 0.45, 0.40),
        width=1.4,
    )


def build_temp_mixed_pdf_file(run_id: str) -> tuple[str, bytes, str, str]:
    """创建 native、scan、native 三页混合 PDF fixture。"""
    native_start, scanned_keyword, native_end = build_mixed_pdf_keywords(run_id)
    document = pymupdf.open()
    scan_source = pymupdf.open()
    try:
        native_start_page = document.new_page(width=595, height=842)
        _insert_pdf_text_lines(
            native_start_page,
            "FirstRAG Mixed PDF - Native Page 1",
            (
                native_start,
                "This page must use the native text parser.",
            ),
        )

        scan_source_page = scan_source.new_page(width=595, height=842)
        _insert_pdf_text_lines(
            scan_source_page,
            "FirstRAG Mixed PDF - Scanned Page 2",
            (
                scanned_keyword,
                "This target exists only in the raster image.",
            ),
        )
        scan_image = scan_source_page.get_pixmap(
            dpi=220,
            alpha=False,
        ).tobytes("png")
        scanned_page = document.new_page(width=595, height=842)
        scanned_page.insert_image(scanned_page.rect, stream=scan_image)

        native_end_page = document.new_page(width=595, height=842)
        _insert_pdf_text_lines(
            native_end_page,
            "FirstRAG Mixed PDF - Native Page 3",
            (
                native_end,
                "This page must remain after the OCR page.",
            ),
        )
        pdf_bytes = document.tobytes(garbage=4, deflate=True)
    finally:
        scan_source.close()
        document.close()

    filename = f"firstrag-mixed-pdf-indexing-eval-{run_id}.pdf"
    return filename, pdf_bytes, "application/pdf", scanned_keyword


def build_temp_file(run_id: str, file_kind: str) -> tuple[str, str | bytes, str, str]:
    """按评测类型构建临时文件。"""
    if file_kind == "image":
        return build_temp_image_file(run_id)
    if file_kind == MIXED_PDF_FILE_KIND:
        return build_temp_mixed_pdf_file(run_id)
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
        "dense_degraded": diagnostics.get("dense_degraded"),
        "dense_errors": diagnostics.get("dense_errors") or [],
        "sparse_degraded": diagnostics.get("sparse_degraded"),
        "sparse_errors": diagnostics.get("sparse_errors") or [],
        "timing": diagnostics.get("timing") or {},
        "llm": diagnostics.get("llm") or {},
        "reason": retrieval.get("reason"),
    }


def _context_page_matches(
    chunks: list[dict[str, Any]],
    *,
    page_number: int,
    parse_method: str,
    expected_keyword: str,
) -> bool:
    """判断 chunk context 是否包含指定页、解析方式和唯一标识。"""
    expected_keyword = expected_keyword.casefold()
    return any(
        chunk.get("location", {}).get("page_number") == page_number
        and chunk.get("location", {}).get("pdf_parse_method") == parse_method
        and expected_keyword in str(chunk.get("content") or "").casefold()
        for chunk in chunks
        if isinstance(chunk, dict)
        and isinstance(chunk.get("location"), dict)
    )


def evaluate_mixed_pdf_result(
    *,
    chat_result: ChatResult,
    source_context: dict[str, Any] | None,
    expected_filename: str,
    expected_keywords: tuple[str, str, str],
    page_preview: PdfPagePreviewEvidence | None,
) -> list[dict[str, Any]]:
    """生成 mixed PDF 页码、解析方式和 chunk 页序检查项。"""
    native_start, scanned_keyword, native_end = expected_keywords
    uploaded_sources = [
        source
        for source in chat_result.sources
        if str(source.get("file_name") or "") == expected_filename
    ]
    scanned_sources = [
        source
        for source in uploaded_sources
        if source.get("page_number") == MIXED_PDF_SCANNED_PAGE_NUMBER
        and source.get("pdf_parse_method") == "ocr"
    ]
    chunks = (
        list(source_context.get("chunks") or [])
        if isinstance(source_context, dict)
        else []
    )
    target_chunks = [
        chunk
        for chunk in chunks
        if isinstance(chunk, dict) and chunk.get("is_target") is True
    ]
    target_is_scanned_page = any(
        isinstance(chunk.get("location"), dict)
        and chunk["location"].get("page_number") == MIXED_PDF_SCANNED_PAGE_NUMBER
        and chunk["location"].get("pdf_parse_method") == "ocr"
        for chunk in target_chunks
    )
    page_chunk_indexes: dict[int, list[int]] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict) or not isinstance(
            chunk.get("location"),
            dict,
        ):
            continue
        page_number = chunk["location"].get("page_number")
        chunk_index = chunk.get("chunk_index")
        if (
            isinstance(page_number, int)
            and not isinstance(page_number, bool)
            and isinstance(chunk_index, int)
            and not isinstance(chunk_index, bool)
        ):
            page_chunk_indexes.setdefault(page_number, []).append(chunk_index)
    page_order_is_stable = (
        all(page_number in page_chunk_indexes for page_number in (1, 2, 3))
        and max(page_chunk_indexes[1]) < min(page_chunk_indexes[2])
        and max(page_chunk_indexes[2]) < min(page_chunk_indexes[3])
    )
    preview_differences = (
        page_preview.page_mean_differences
        if page_preview is not None
        else {}
    )
    sorted_preview_differences = sorted(preview_differences.values())
    preview_has_clear_page_match = (
        len(sorted_preview_differences) >= 2
        and sorted_preview_differences[1] - sorted_preview_differences[0] >= 0.002
    )

    return [
        {
            "name": "mixed_pdf_source_points_to_scanned_page",
            "passed": bool(scanned_sources),
            "expected": {
                "page_number": MIXED_PDF_SCANNED_PAGE_NUMBER,
                "pdf_parse_method": "ocr",
            },
            "actual": [
                {
                    "page_number": source.get("page_number"),
                    "pdf_parse_method": source.get("pdf_parse_method"),
                    "chunk_index": source.get("chunk_index"),
                }
                for source in uploaded_sources
            ],
        },
        {
            "name": "mixed_pdf_context_target_is_scanned_page",
            "passed": target_is_scanned_page,
            "expected": {
                "page_number": MIXED_PDF_SCANNED_PAGE_NUMBER,
                "pdf_parse_method": "ocr",
            },
            "actual": [
                {
                    "chunk_index": chunk.get("chunk_index"),
                    "location": chunk.get("location"),
                }
                for chunk in target_chunks
            ],
        },
        {
            "name": "mixed_pdf_context_has_native_page_1",
            "passed": _context_page_matches(
                chunks,
                page_number=1,
                parse_method="native_text",
                expected_keyword=native_start,
            ),
            "expected": native_start,
            "actual": page_chunk_indexes.get(1, []),
        },
        {
            "name": "mixed_pdf_context_has_ocr_page_2",
            "passed": _context_page_matches(
                chunks,
                page_number=2,
                parse_method="ocr",
                expected_keyword=scanned_keyword,
            ),
            "expected": scanned_keyword,
            "actual": page_chunk_indexes.get(2, []),
        },
        {
            "name": "mixed_pdf_context_has_native_page_3",
            "passed": _context_page_matches(
                chunks,
                page_number=3,
                parse_method="native_text",
                expected_keyword=native_end,
            ),
            "expected": native_end,
            "actual": page_chunk_indexes.get(3, []),
        },
        {
            "name": "mixed_pdf_context_preserves_page_order",
            "passed": page_order_is_stable,
            "expected": "page 1 chunks < page 2 chunks < page 3 chunks",
            "actual": page_chunk_indexes,
        },
        {
            "name": "mixed_pdf_page_preview_is_private_png",
            "passed": bool(
                page_preview is not None
                and page_preview.content_type.lower().startswith("image/png")
                and "private" in page_preview.cache_control.lower()
                and page_preview.width > 0
                and page_preview.height > 0
                and max(page_preview.width, page_preview.height) <= 1800
            ),
            "expected": {
                "content_type": "image/png",
                "cache_control": "private",
                "max_dimension": 1800,
            },
            "actual": (
                {
                    "content_type": page_preview.content_type,
                    "cache_control": page_preview.cache_control,
                    "content_disposition": page_preview.content_disposition,
                    "width": page_preview.width,
                    "height": page_preview.height,
                }
                if page_preview is not None
                else None
            ),
        },
        {
            "name": "mixed_pdf_page_preview_matches_page_2",
            "passed": bool(
                page_preview is not None
                and page_preview.closest_page_number
                == MIXED_PDF_SCANNED_PAGE_NUMBER
                and preview_has_clear_page_match
            ),
            "expected": {
                "closest_page_number": MIXED_PDF_SCANNED_PAGE_NUMBER,
                "minimum_difference_margin": 0.002,
            },
            "actual": (
                {
                    "closest_page_number": page_preview.closest_page_number,
                    "page_mean_differences": preview_differences,
                }
                if page_preview is not None
                else None
            ),
        },
    ]


def evaluate_result(
    *,
    upload_response: dict[str, Any],
    file_record: dict[str, Any] | None,
    job: dict[str, Any],
    chat_result: ChatResult,
    expected_filename: str,
    expected_keyword: str,
    file_kind: str = "markdown",
    source_context: dict[str, Any] | None = None,
    mixed_pdf_keywords: tuple[str, str, str] | None = None,
    page_preview: PdfPagePreviewEvidence | None = None,
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
    uploaded_file_has_dense_sparse_source = any(
        "dense" in channels and "sparse" in channels
        for channels in uploaded_file_source_channels
    )
    answer = chat_result.answer
    diagnostics = compact_diagnostics(chat_result.retrieval)
    checks = [
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
            "name": "chat_dense_sparse_not_degraded",
            "passed": (
                diagnostics["dense_degraded"] is not True
                and diagnostics["sparse_degraded"] is not True
            ),
            "expected": {"dense_degraded": False, "sparse_degraded": False},
            "actual": {
                "dense_degraded": diagnostics["dense_degraded"],
                "dense_errors": diagnostics["dense_errors"],
                "sparse_degraded": diagnostics["sparse_degraded"],
                "sparse_errors": diagnostics["sparse_errors"],
            },
        },
        {
            "name": "uploaded_file_source_uses_dense_sparse",
            "passed": uploaded_file_has_dense_sparse_source,
            "expected": ["dense", "sparse"],
            "actual": uploaded_file_source_channels,
        },
        {
            "name": "answer_contains_eval_keyword",
            "passed": expected_keyword.lower() in answer.lower(),
            "expected": expected_keyword,
            "actual": answer[:500],
        },
    ]
    if file_kind == MIXED_PDF_FILE_KIND:
        checks.extend(evaluate_mixed_pdf_result(
            chat_result=chat_result,
            source_context=source_context,
            expected_filename=expected_filename,
            expected_keywords=(
                mixed_pdf_keywords
                if mixed_pdf_keywords is not None
                else ("", expected_keyword, "")
            ),
            page_preview=page_preview,
        ))
    return checks


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
    file_kind: str = "markdown",
    source_context: dict[str, Any] | None = None,
    page_preview: PdfPagePreviewEvidence | None = None,
) -> dict[str, Any]:
    """构建历史 JSON 记录。"""
    diagnostics = compact_diagnostics(chat_result.retrieval)
    return {
        "schema_version": 3,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "base_url": base_url,
        "knowledge_base": {
            "id": knowledge_base.get("id"),
            "name": knowledge_base.get("name"),
        },
        "file": {
            "id": file_id,
            "original_name": filename,
            "kind": file_kind,
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
                    "page_number": source.get("page_number"),
                    "pdf_parse_method": source.get("pdf_parse_method"),
                    "retrieval_sources": source.get("retrieval_sources") or [],
                    "rerank_score": source.get("rerank_score"),
                }
                for source in chat_result.sources
            ],
        },
        "source_context": {
            "target_chunk_index": source_context.get("target_chunk_index"),
            "chunks": [
                {
                    "chunk_index": chunk.get("chunk_index"),
                    "location": chunk.get("location") or {},
                    "content_preview": str(chunk.get("content") or "")[:300],
                    "is_target": chunk.get("is_target") is True,
                }
                for chunk in source_context.get("chunks") or []
                if isinstance(chunk, dict)
            ],
        } if isinstance(source_context, dict) else None,
        "page_preview": (
            {
                "content_type": page_preview.content_type,
                "cache_control": page_preview.cache_control,
                "content_disposition": page_preview.content_disposition,
                "width": page_preview.width,
                "height": page_preview.height,
                "closest_page_number": page_preview.closest_page_number,
                "page_mean_differences": page_preview.page_mean_differences,
            }
            if page_preview is not None
            else None
        ),
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
        f"- 文件类型：{run_record['file'].get('kind', 'markdown')}",
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
        f"- Dense 降级：{diagnostics['dense_degraded']}",
        f"- Dense 错误：{diagnostics['dense_errors'] or '—'}",
        f"- Sparse 降级：{diagnostics['sparse_degraded']}",
        f"- Sparse 错误：{diagnostics['sparse_errors'] or '—'}",
        "- LLM：provider={provider}，model={model}，tokens={tokens}".format(
            provider=diagnostics["llm"].get("provider", "—"),
            model=diagnostics["llm"].get("model", "—"),
            tokens=diagnostics["llm"].get("total_tokens") or "—",
        ),
        f"- 判断原因：{diagnostics['reason'] or '—'}",
        "",
        "## 引用",
        "",
    ])
    if chat["sources"]:
        for index, source in enumerate(chat["sources"], 1):
            lines.append(
                "- {index}. {file_name} / chunk #{chunk_index} / page={page_number} "
                "/ method={parse_method} / sources={sources} / rerank={rerank}".format(
                    index=index,
                    file_name=source.get("file_name") or "未知文件",
                    chunk_index=source.get("chunk_index", "—"),
                    page_number=source.get("page_number", "—"),
                    parse_method=source.get("pdf_parse_method", "—"),
                    sources=source.get("retrieval_sources") or [],
                    rerank=source.get("rerank_score", "—"),
                ),
            )
    else:
        lines.append("- 无")

    source_context = run_record.get("source_context")
    if isinstance(source_context, dict):
        lines.extend([
            "",
            "## 引用原文上下文",
            "",
            f"- Target chunk: {source_context.get('target_chunk_index')}",
        ])
        for chunk in source_context.get("chunks") or []:
            location = chunk.get("location") or {}
            lines.append(
                "- chunk #{chunk_index}: page={page_number}, "
                "method={parse_method}, target={is_target}".format(
                    chunk_index=chunk.get("chunk_index"),
                    page_number=location.get("page_number"),
                    parse_method=location.get("pdf_parse_method"),
                    is_target=chunk.get("is_target"),
                ),
            )

    page_preview = run_record.get("page_preview")
    if isinstance(page_preview, dict):
        lines.extend([
            "",
            "## PDF 页预览",
            "",
            f"- Content-Type：{page_preview.get('content_type') or '—'}",
            f"- Cache-Control：{page_preview.get('cache_control') or '—'}",
            "- 尺寸：{width}×{height}".format(
                width=page_preview.get("width"),
                height=page_preview.get("height"),
            ),
            f"- 最匹配原始页：第 {page_preview.get('closest_page_number')} 页",
            f"- 各页平均像素差：{page_preview.get('page_mean_differences')}",
        ])

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
    if args.keep_file and args.permanent_delete:
        raise EvalError("--keep-file 与 --permanent-delete 不能同时使用")

    generated_at = datetime.now()
    run_id = generated_at.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    base_url = normalize_base_url(args.base_url)
    filename, file_content, content_type, keyword = build_temp_file(
        run_id,
        args.file_kind,
    )
    mixed_pdf_keywords = (
        build_mixed_pdf_keywords(run_id)
        if args.file_kind == MIXED_PDF_FILE_KIND
        else None
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
    original_retrieval_settings: dict[str, Any] | None = None
    source_context: dict[str, Any] | None = None
    page_preview: PdfPagePreviewEvidence | None = None
    retrieval_settings_restored = False
    cleanup_verified = False
    cleanup_done = False
    permanent_delete_vector_count: int | None = None
    vector_user_id: int | None = None
    vector_store: Any | None = None
    lifecycle_checks: list[dict[str, Any]] = []
    if args.exercise_vector_lifecycle or args.permanent_delete:
        vector_user_id, vector_store = build_eval_vector_store(args.username)
    try:
        original_retrieval_settings = get_retrieval_settings(
            base_url=base_url,
            token=token,
            knowledge_base_id=knowledge_base_id,
            timeout=args.timeout,
        )
        update_retrieval_settings(
            base_url=base_url,
            token=token,
            knowledge_base_id=knowledge_base_id,
            settings=INDEXING_EVAL_RETRIEVAL_SETTINGS,
            timeout=args.timeout,
        )
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
        if args.exercise_vector_lifecycle:
            if vector_store is None or vector_user_id is None:
                raise EvalError("vector lifecycle adapter 未初始化")
            initial_diagnostics = compact_diagnostics(chat_result.retrieval)
            initial_sources = [
                source
                for source in chat_result.sources
                if str(source.get("file_name") or "") == filename
            ]
            initial_count = count_eval_file_vectors(
                vector_store,
                user_id=vector_user_id,
                file_id=uploaded_file_id,
            )
            request_json(
                "DELETE",
                base_url,
                f"/chat/knowledge-files/{uploaded_file_id}/vectors",
                token=token,
                timeout=args.timeout,
            )
            deleted_count = count_eval_file_vectors(
                vector_store,
                user_id=vector_user_id,
                file_id=uploaded_file_id,
            )
            deleted_file_record = find_file_in_knowledge_base(
                base_url=base_url,
                token=token,
                knowledge_base_id=knowledge_base_id,
                file_id=uploaded_file_id,
                timeout=args.timeout,
            )
            reindex_started_at = time.monotonic()
            reindex_response = request_json(
                "POST",
                base_url,
                f"/chat/knowledge-files/{uploaded_file_id}/vectors",
                token=token,
                timeout=args.timeout,
            )
            reindex_job = reindex_response.get("job") or {}
            reindex_job_id = str(reindex_job.get("id") or "")
            if not reindex_job_id:
                raise EvalError("重新向量化响应中没有 job id")
            completed_job = wait_for_job(
                base_url=base_url,
                token=token,
                job_id=reindex_job_id,
                timeout=args.job_timeout,
                poll_interval=args.poll_interval,
                request_timeout=args.timeout,
            )
            reindex_elapsed_seconds = time.monotonic() - reindex_started_at
            recovered_count = count_eval_file_vectors(
                vector_store,
                user_id=vector_user_id,
                file_id=uploaded_file_id,
            )
            file_record = find_file_in_knowledge_base(
                base_url=base_url,
                token=token,
                knowledge_base_id=knowledge_base_id,
                file_id=uploaded_file_id,
                timeout=args.timeout,
            )
            recovered_conversation_id = create_conversation(
                base_url=base_url,
                token=token,
                knowledge_base_id=knowledge_base_id,
                run_id=f"{run_id}-recovered",
                timeout=args.timeout,
            )
            chat_result = stream_chat(
                base_url=base_url,
                token=token,
                knowledge_base_id=knowledge_base_id,
                conversation_id=recovered_conversation_id,
                question=question,
                timeout=args.timeout,
            )
            recovered_diagnostics = compact_diagnostics(chat_result.retrieval)
            recovered_sources = [
                source
                for source in chat_result.sources
                if str(source.get("file_name") or "") == filename
            ]
            lifecycle_checks.extend([
                {
                    "name": "initial_vector_count_positive",
                    "passed": initial_count > 0,
                    "expected": "> 0",
                    "actual": initial_count,
                },
                {
                    "name": "initial_hybrid_retrieval_healthy",
                    "passed": bool(
                        initial_diagnostics["dense_degraded"] is not True
                        and initial_diagnostics["sparse_degraded"] is not True
                        and any(
                            "dense" in (source.get("retrieval_sources") or [])
                            and "sparse" in (source.get("retrieval_sources") or [])
                            for source in initial_sources
                        )
                    ),
                    "expected": "dense+sparse source without degradation",
                    "actual": {
                        "dense_degraded": initial_diagnostics["dense_degraded"],
                        "sparse_degraded": initial_diagnostics["sparse_degraded"],
                        "source_count": len(initial_sources),
                    },
                },
                {
                    "name": "vector_delete_clears_entries",
                    "passed": deleted_count == 0,
                    "expected": 0,
                    "actual": deleted_count,
                },
                {
                    "name": "vector_delete_resets_file_pending",
                    "passed": (deleted_file_record or {}).get("status") == "pending",
                    "expected": "pending",
                    "actual": (deleted_file_record or {}).get("status"),
                },
                {
                    "name": "reindex_restores_entries",
                    "passed": recovered_count > 0,
                    "expected": "> 0",
                    "actual": {
                        "count": recovered_count,
                        "elapsed_seconds": round(reindex_elapsed_seconds, 3),
                    },
                },
                {
                    "name": "reindex_hybrid_retrieval_healthy",
                    "passed": bool(
                        recovered_diagnostics["dense_degraded"] is not True
                        and recovered_diagnostics["sparse_degraded"] is not True
                        and any(
                            "dense" in (source.get("retrieval_sources") or [])
                            and "sparse" in (source.get("retrieval_sources") or [])
                            for source in recovered_sources
                        )
                    ),
                    "expected": "dense+sparse source without degradation",
                    "actual": {
                        "dense_degraded": recovered_diagnostics["dense_degraded"],
                        "sparse_degraded": recovered_diagnostics["sparse_degraded"],
                        "source_count": len(recovered_sources),
                    },
                },
            ])
        if args.file_kind == MIXED_PDF_FILE_KIND:
            scanned_source = next(
                (
                    source
                    for source in chat_result.sources
                    if str(source.get("file_name") or "") == filename
                    and source.get("page_number")
                    == MIXED_PDF_SCANNED_PAGE_NUMBER
                    and isinstance(source.get("chunk_index"), int)
                    and not isinstance(source.get("chunk_index"), bool)
                ),
                None,
            )
            if scanned_source is not None:
                source_context = get_source_chunk_context(
                    base_url=base_url,
                    token=token,
                    file_id=uploaded_file_id,
                    chunk_index=int(scanned_source["chunk_index"]),
                    timeout=args.timeout,
                )
                preview_content, preview_headers = request_binary(
                    "GET",
                    base_url,
                    (
                        f"/chat/knowledge-files/{uploaded_file_id}/pages/"
                        f"{MIXED_PDF_SCANNED_PAGE_NUMBER}/preview"
                    ),
                    token=token,
                    timeout=args.timeout,
                )
                if not isinstance(file_content, bytes):
                    raise EvalError("mixed PDF fixture 不是二进制内容")
                page_preview = inspect_pdf_page_preview(
                    preview_content=preview_content,
                    response_headers=preview_headers,
                    pdf_content=file_content,
                )
        checks = evaluate_result(
            upload_response=upload_response,
            file_record=file_record,
            job=completed_job,
            chat_result=chat_result,
            expected_filename=filename,
            expected_keyword=keyword,
            file_kind=args.file_kind,
            source_context=source_context,
            mixed_pdf_keywords=mixed_pdf_keywords,
            page_preview=page_preview,
        )
        checks.extend(lifecycle_checks)
    finally:
        if original_retrieval_settings is not None:
            try:
                update_retrieval_settings(
                    base_url=base_url,
                    token=token,
                    knowledge_base_id=knowledge_base_id,
                    settings=original_retrieval_settings,
                    timeout=args.timeout,
                )
                restored_settings = get_retrieval_settings(
                    base_url=base_url,
                    token=token,
                    knowledge_base_id=knowledge_base_id,
                    timeout=args.timeout,
                )
                retrieval_settings_restored = (
                    restored_settings == original_retrieval_settings
                )
            except Exception as exc:
                print(
                    f"Warning: failed to restore retrieval settings: {exc}",
                    file=sys.stderr,
                )
        if uploaded_file_id and not args.keep_file:
            try:
                if args.permanent_delete:
                    permanently_delete_file(
                        base_url=base_url,
                        token=token,
                        file_id=uploaded_file_id,
                        timeout=args.timeout,
                    )
                    if vector_store is None or vector_user_id is None:
                        raise EvalError("永久删除验收 adapter 未初始化")
                    permanent_delete_vector_count = count_eval_file_vectors(
                        vector_store,
                        user_id=vector_user_id,
                        file_id=uploaded_file_id,
                    )
                else:
                    remove_file_relation(
                        base_url=base_url,
                        token=token,
                        knowledge_base_id=knowledge_base_id,
                        file_id=uploaded_file_id,
                        timeout=args.timeout,
                    )
                cleanup_verified = find_file_in_knowledge_base(
                    base_url=base_url,
                    token=token,
                    knowledge_base_id=knowledge_base_id,
                    file_id=uploaded_file_id,
                    timeout=args.timeout,
                ) is None
                cleanup_done = cleanup_verified
            except EvalError as exc:
                print(f"清理临时文件关联失败：{exc}", file=sys.stderr)

    checks.append({
        "name": "retrieval_settings_restored",
        "passed": retrieval_settings_restored,
        "expected": True,
        "actual": retrieval_settings_restored,
    })
    if not args.keep_file:
        checks.append({
            "name": (
                "temporary_file_permanently_deleted"
                if args.permanent_delete
                else "temporary_file_relation_removed"
            ),
            "passed": cleanup_verified,
            "expected": True,
            "actual": cleanup_verified,
        })
    if args.permanent_delete:
        checks.append({
            "name": "permanent_delete_clears_vectors",
            "passed": permanent_delete_vector_count == 0,
            "expected": 0,
            "actual": permanent_delete_vector_count,
        })

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
        file_kind=args.file_kind,
        source_context=source_context,
        page_preview=page_preview,
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
