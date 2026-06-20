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

    try:
        for event in stream_rag_response(
            chain=chain,
            user_input=user_input,
            chat_history=history,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        ):
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
        )
        raise
    except Exception:
        logger.exception("流式回答生成失败")
        finish_assistant_message(
            assistant_message_id,
            full_answer,
            "failed",
            "回答生成失败，请稍后重试",
        )
        yield format_sse_event("error", {
            "message": "回答生成失败，请稍后重试",
            "partial_answer": full_answer,
        })
        return

    finish_assistant_message(assistant_message_id, full_answer, "completed")
    yield format_sse_event("done", {
        "message": "回答完成",
        "answer": full_answer,
        "sources": sources,
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
