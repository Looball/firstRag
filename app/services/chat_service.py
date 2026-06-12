from collections.abc import Iterator

from app.repositories.message_repository import (
    create_message,
    get_conversation_messages,
)
from app.services.rag_service import get_answer


# 定义存储聊天消息的函数
def save_message(conversation_id: str, role: str, content: str) -> None:
    create_message(conversation_id, role, content)


# 返回answer流式消息生成器，在生成器迭代完后，将answer保存到messages表
def stream_answer_and_save(
    chain,
    user_input: str,
    history: list,
    conversation_id: str,
) -> Iterator[str]:
    full_answer = ""

    for chunk in get_answer(chain, user_input, history):
        full_answer += chunk
        yield chunk

    save_message(conversation_id, "assistant", full_answer)


# 将聊天历史转换为LangChain能够处理的元组列表格式
def load_chat_history(conversation_id: str) -> list[tuple[str, str]]:
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
