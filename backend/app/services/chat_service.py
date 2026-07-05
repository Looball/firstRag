import json
import logging
from collections.abc import Iterator
from time import perf_counter
from typing import Any
from uuid import UUID

from app.core.observability import (
    get_request_context,
    log_exception_event,
    log_structured_event,
)
from app.repositories.message_repository import (
    create_message,
    finish_assistant_message,
    get_conversation_messages,
)
from app.services.rag_service import stream_rag_response

logger = logging.getLogger(__name__)


LOCAL_GREETING_RESPONSES = {
    "你好": "你好！有什么可以帮你的吗？",
    "您好": "您好！有什么可以帮您的吗？",
    "嗨": "嗨！有什么可以帮你的吗？",
    "hi": "Hi！有什么可以帮你的吗？",
    "hello": "Hello！有什么可以帮你的吗？",
}


def normalize_local_chat_input(user_input: str) -> str:
    """标准化本地短路判断使用的用户输入。"""
    return user_input.strip().strip("。！？!?~～.，, ")


def get_local_chat_response(user_input: str) -> str | None:
    """返回无需模型调用的本地闲聊回复。"""
    normalized_input = normalize_local_chat_input(user_input)
    return LOCAL_GREETING_RESPONSES.get(normalized_input.lower()) or (
        LOCAL_GREETING_RESPONSES.get(normalized_input)
    )


def save_message(
    conversation_id: UUID,
    role: str,
    content: str,
    status: str = "completed",
) -> dict[str, Any]:
    """保存一条消息，并返回数据库生成的记录标识。"""
    message = create_message(conversation_id, role, content, status)
    if message is None:
        raise RuntimeError("消息保存失败")
    return dict(message)


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """将事件数据格式化为 Server-Sent Events 文本。"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def record_stream_timing(
    retrieval: dict[str, Any],
    name: str,
    started_at: float,
) -> None:
    """将聊天流式阶段耗时写入 retrieval diagnostics。"""
    diagnostics = retrieval.setdefault("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        retrieval["diagnostics"] = diagnostics

    timing = diagnostics.setdefault("timing", {})
    if not isinstance(timing, dict):
        timing = {}
        diagnostics["timing"] = timing

    timing[f"{name}_ms"] = round((perf_counter() - started_at) * 1000, 2)


def merge_llm_diagnostics(
    retrieval: dict[str, Any],
    llm_diagnostics: dict[str, Any] | None,
) -> None:
    """将流式过程中后到达的 LLM usage 合并进 retrieval diagnostics。"""
    if not isinstance(llm_diagnostics, dict):
        return

    diagnostics = retrieval.setdefault("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        retrieval["diagnostics"] = diagnostics

    current_llm = diagnostics.get("llm")
    if not isinstance(current_llm, dict):
        current_llm = {}
    diagnostics["llm"] = {
        **current_llm,
        **llm_diagnostics,
    }


def stream_answer_and_save(
    chain,
    user_input: str,
    history: list,
    conversation_id: UUID,
    assistant_message_id: UUID,
    user_id: int,
    knowledge_base_id: UUID,
    image_attachments: list[dict] | None = None,
    request_id: str | None = None,
) -> Iterator[str]:
    """流式返回答案和引用文档，并更新助手消息的生成状态。

    流式过程中先发送 sources 事件（引用文档），再逐片发送 answer
    事件。正常结束后保存完整回答；错误或客户端断开时保存部分回答和状态。
    """
    full_answer = ""
    sources: list[dict] = []
    retrieval: dict[str, Any] = {}
    stream_started_at = perf_counter()
    answer_started_at: float | None = None
    log_context = {
        "request_id": request_id or get_request_context().get("request_id"),
        "user_id": user_id,
        "conversation_id": str(conversation_id),
        "knowledge_base_id": str(knowledge_base_id),
        "message_id": str(assistant_message_id),
    }

    try:
        for event in stream_rag_response(
            chain=chain,
            user_input=user_input,
            chat_history=history,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            image_attachments=image_attachments,
        ):
            if event["type"] == "retrieval":
                retrieval = {
                    "need_retrieval": event["need_retrieval"],
                    "rewritten_query": event["rewritten_query"],
                    "reason": event["reason"],
                    "retrieved_count": event["retrieved_count"],
                    "source_count": event["source_count"],
                }
                for optional_key in (
                    "final_need_retrieval",
                    "llm_need_retrieval",
                    "llm_reason",
                    "override_applied",
                    "override_reason",
                    "retrieval_sources",
                    "vector_degraded",
                    "diagnostics",
                ):
                    if optional_key in event:
                        retrieval[optional_key] = event[optional_key]
                yield format_sse_event("retrieval", {
                    **retrieval,
                })
                continue

            if event["type"] == "sources":
                sources = event["sources"]
                yield format_sse_event("sources", {
                    "sources": sources,
                })
                continue

            if event["type"] == "llm_usage":
                merge_llm_diagnostics(retrieval, event.get("llm"))
                yield format_sse_event("llm_usage", {
                    "llm": event.get("llm") or {},
                })
                continue

            if event["type"] == "answer":
                if answer_started_at is None:
                    record_stream_timing(
                        retrieval,
                        "first_answer_token",
                        stream_started_at,
                    )
                    first_token_ms = (
                        retrieval.get("diagnostics", {})
                        .get("timing", {})
                        .get("first_answer_token_ms")
                    )
                    log_structured_event(
                        logger,
                        logging.INFO,
                        "chat_first_answer_token",
                        **log_context,
                        duration_ms=first_token_ms,
                    )
                    answer_started_at = perf_counter()
                content = event["content"]
                full_answer += content
                yield format_sse_event("answer", {
                    "content": content,
                })
    except GeneratorExit:
        record_stream_timing(retrieval, "chat_stream_total", stream_started_at)
        if answer_started_at is not None:
            record_stream_timing(retrieval, "answer_stream", answer_started_at)
        timing = retrieval.get("diagnostics", {}).get("timing", {})
        log_structured_event(
            logger,
            logging.WARNING,
            "chat_stream_cancelled",
            **log_context,
            status="cancelled",
            duration_ms=timing.get("chat_stream_total_ms"),
            source_count=len(sources),
            answer_started=answer_started_at is not None,
            message="客户端中断了流式连接",
        )
        finish_assistant_message(
            assistant_message_id,
            full_answer,
            "cancelled",
            "客户端中断了流式连接",
            sources,
            retrieval,
        )
        raise
    except Exception as exc:
        record_stream_timing(retrieval, "chat_stream_total", stream_started_at)
        if answer_started_at is not None:
            record_stream_timing(retrieval, "answer_stream", answer_started_at)
        timing = retrieval.get("diagnostics", {}).get("timing", {})
        log_exception_event(
            logger,
            "chat_stream_failed",
            exc,
            default_source="chat_stream",
            **log_context,
            status="failed",
            duration_ms=timing.get("chat_stream_total_ms"),
            source_count=len(sources),
            answer_started=answer_started_at is not None,
            message="流式回答生成失败",
        )
        finish_assistant_message(
            assistant_message_id,
            full_answer,
            "failed",
            "回答生成失败，请稍后重试",
            sources,
            retrieval,
        )
        yield format_sse_event("error", {
            "message": "回答生成失败，请稍后重试",
            "partial_answer": full_answer,
        })
        return

    record_stream_timing(retrieval, "chat_stream_total", stream_started_at)
    if answer_started_at is not None:
        record_stream_timing(retrieval, "answer_stream", answer_started_at)
    timing = retrieval.get("diagnostics", {}).get("timing", {})
    log_structured_event(
        logger,
        logging.INFO,
        "chat_stream_completed",
        **log_context,
        status="completed",
        duration_ms=timing.get("chat_stream_total_ms"),
        first_answer_token_ms=timing.get("first_answer_token_ms"),
        source_count=len(sources),
        retrieved_count=retrieval.get("retrieved_count"),
        need_retrieval=retrieval.get("need_retrieval"),
    )
    finish_assistant_message(
        assistant_message_id,
        full_answer,
        "completed",
        sources=sources,
        retrieval=retrieval,
    )
    yield format_sse_event("done", {
        "message": "回答完成",
        "answer": full_answer,
        "sources": sources,
        "message_id": str(assistant_message_id),
    })


def stream_local_answer_and_save(
    answer: str,
    assistant_message_id: UUID,
) -> Iterator[str]:
    """流式返回本地短路答案，并完成助手消息保存。"""
    retrieval = {
        "need_retrieval": False,
        "final_need_retrieval": False,
        "llm_need_retrieval": False,
        "rewritten_query": "",
        "reason": "本地识别为普通问候，跳过模型调用和知识库检索",
        "llm_reason": "本地识别为普通问候",
        "override_applied": False,
        "override_reason": "",
        "retrieved_count": 0,
        "source_count": 0,
    }
    yield format_sse_event("retrieval", retrieval)
    yield format_sse_event("answer", {
        "content": answer,
    })
    finish_assistant_message(
        assistant_message_id,
        answer,
        "completed",
        sources=[],
        retrieval=retrieval,
    )
    yield format_sse_event("done", {
        "message": "回答完成",
        "answer": answer,
        "sources": [],
        "message_id": str(assistant_message_id),
    })


# 将聊天历史转换为LangChain能够处理的元组列表格式
def load_chat_history(conversation_id: UUID) -> list[tuple[str, str]]:
    rows = get_conversation_messages(conversation_id)
    role_map = {
        "user": "human",
        "assistant": "ai",
    }
    return [
        (role_map[row["role"]], row["content"])
        for row in rows
        if row["role"] in role_map
    ]
