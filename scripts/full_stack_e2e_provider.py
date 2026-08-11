"""为无外部密钥的全栈 E2E 提供确定性 OpenAI-compatible 响应。"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


APP = FastAPI(title="FirstRAG Full-stack E2E Provider")
MODEL_NAME = "firstrag-e2e-model"
ANSWER = "FirstRAG 全栈验收标识是 T089 FULL STACK SOURCE。"
EMBEDDING_DIMENSIONS = 16
INDEXING_MARKER_PATTERN = re.compile(r"FirstRAGIndexingEval-[0-9A-Za-z-]+")


class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embedding 请求。"""

    model: str
    input: str | list[str]
    dimensions: int | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion 请求。"""

    model: str
    messages: list[dict[str, Any]]
    stream: bool = False


def _embedding_vector(dimensions: int) -> list[float]:
    """生成固定单位向量，让文档和 query 可稳定进入 vector 召回。"""
    return [1.0, *([0.0] * (dimensions - 1))]


def _answer_for_request(request: ChatCompletionRequest) -> str:
    """按验收问题中的唯一 marker 返回确定性答案。"""
    for message in reversed(request.messages):
        content = str(message.get("content") or "")
        match = INDEXING_MARKER_PATTERN.search(content)
        if match:
            return f"FirstRAG 索引验收标识是 {match.group(0)}。"
    return ANSWER


def _stream_chat_completion(request: ChatCompletionRequest, answer: str):
    """按 OpenAI SSE 协议流式返回确定性回答。"""
    completion_id = f"chatcmpl-{uuid4().hex}"
    created_at = int(time.time())
    chunks = (
        {"role": "assistant"},
        {"content": answer},
    )
    for delta in chunks:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_at,
            "model": request.model,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": None,
            }],
        }
        yield f"data: {json.dumps(payload)}\n\n"

    final_payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_at,
        "model": request.model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 8,
            "total_tokens": 16,
        },
    }
    yield f"data: {json.dumps(final_payload)}\n\n"
    yield "data: [DONE]\n\n"


@APP.get("/health")
def health() -> dict[str, bool]:
    """返回 provider stub 健康状态。"""
    return {"ok": True}


@APP.get("/v1/models")
def list_models() -> dict[str, object]:
    """返回 seed 配置使用的确定性模型。"""
    return {
        "object": "list",
        "data": [{"id": MODEL_NAME, "object": "model"}],
    }


@APP.post("/v1/embeddings")
def create_embeddings(request: EmbeddingRequest) -> dict[str, object]:
    """返回与输入条数一致的固定 embedding。"""
    inputs = request.input if isinstance(request.input, list) else [request.input]
    dimensions = request.dimensions or EMBEDDING_DIMENSIONS
    return {
        "object": "list",
        "model": request.model,
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": _embedding_vector(dimensions),
            }
            for index, _ in enumerate(inputs)
        ],
        "usage": {
            "prompt_tokens": len(inputs),
            "total_tokens": len(inputs),
        },
    }


@APP.post("/v1/chat/completions", response_model=None)
def create_chat_completion(
    request: ChatCompletionRequest,
) -> dict[str, object] | StreamingResponse:
    """返回普通或流式 chat completion。"""
    answer = _answer_for_request(request)
    if request.stream:
        return StreamingResponse(
            _stream_chat_completion(request, answer),
            media_type="text/event-stream",
        )
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 8,
            "total_tokens": 16,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(APP, host="0.0.0.0", port=8080)
