import json
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from app.repositories.message_repository import (
    create_message,
    get_conversation_messages,
)
from app.services.rag_service import stream_rag_response

# 定义存储聊天消息的函数
def save_message(conversation_id: UUID, role: str, content: str) -> None:
    create_message(conversation_id, role, content)


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """将事件数据格式化为 Server-Sent Events 文本。"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# 返回answer流式消息生成器，在生成器迭代完后，将answer保存到messages表
def stream_answer_and_save(
    chain,
    user_input: str,
    history: list,
    conversation_id: UUID,
    user_id: int,
    knowledge_base_id: UUID,
) -> Iterator[str]:
    """流式返回答案和引用文档，并在结束后保存助手回答。"""
    full_answer = ""

    for event in stream_rag_response(
        chain=chain,
        user_input=user_input,
        chat_history=history,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    ):
        if event["type"] == "sources":
            yield format_sse_event("sources", {
                "sources": event["sources"],
            })
            continue

        if event["type"] == "answer":
            content = event["content"]
            full_answer += content
            yield format_sse_event("answer", {
                "content": content,
            })

    save_message(conversation_id, "assistant", full_answer)
    yield format_sse_event("done", {
        "message": "回答完成",
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
