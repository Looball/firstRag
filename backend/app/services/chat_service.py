import json
import logging
from collections.abc import Iterator
from typing import Any
from uuid import UUID

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


def stream_answer_and_save(
    chain,
    user_input: str,
    history: list,
    conversation_id: UUID,
    assistant_message_id: UUID,
    user_id: int,
    knowledge_base_id: UUID,
) -> Iterator[str]:
    """流式返回答案和引用文档，并更新助手消息的生成状态。

    流式过程中先发送 sources 事件（引用文档），再逐片发送 answer
    事件。正常结束后保存完整回答；错误或客户端断开时保存部分回答和状态。
    """
    full_answer = ""
    sources: list[dict] = []
    retrieval: dict[str, Any] = {}

    try:
        for event in stream_rag_response(
            chain=chain,
            user_input=user_input,
            chat_history=history,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
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

            if event["type"] == "answer":
                content = event["content"]
                full_answer += content
                yield format_sse_event("answer", {
                    "content": content,
                })
    except GeneratorExit:
        finish_assistant_message(
            assistant_message_id,
            full_answer,
            "cancelled",
            "客户端中断了流式连接",
            sources,
            retrieval,
        )
        raise
    except Exception:
        logger.exception("流式回答生成失败")
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
