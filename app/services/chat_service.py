from collections.abc import Iterator

from assistant import get_answer
from SqlStatement.query import exe_sql


def save_message(conversation_id: str, role: str, content: str) -> None:
    sql = """
    INSERT INTO messages (conversation_id, role, content)
    VALUES (%s, %s, %s)
    RETURNING id;
    """
    exe_sql(sql_statement=sql, args_tuple=(conversation_id, role, content))


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


def load_chat_history(conversation_id: str) -> list[tuple[str, str]]:
    sql = """
    SELECT role, content
    FROM messages
    WHERE conversation_id = %s
    ORDER BY created_at ASC, id ASC;
    """
    rows = exe_sql(sql_statement=sql, args_tuple=(conversation_id,))
    role_map = {
        "user": "human",
        "assistant": "ai",
    }
    return [
        (role_map[row["role"]], row["content"])
        for row in rows
        if row["role"] in role_map
    ]
