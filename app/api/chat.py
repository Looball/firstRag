from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from assistant import get_chain
from app.core.security import get_current_user_id
from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    load_chat_history,
    save_message,
    stream_answer_and_save,
)
from SqlStatement.query import exe_sql


router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
) -> StreamingResponse:
    if not req.message:
        raise HTTPException(status_code=400, detail="message不能为空")

    conversation_exists = exe_sql(
        sql_statement="""
        SELECT id
        FROM conversations
        WHERE user_id = %s AND id = %s
        """,
        args_tuple=(user_id, req.conversation_id),
    )
    if not conversation_exists:
        raise HTTPException(status_code=404, detail="会话不存在")

    history = load_chat_history(req.conversation_id)
    save_message(req.conversation_id, "user", req.message)
    chain = get_chain()

    return StreamingResponse(
        stream_answer_and_save(
            chain=chain,
            user_input=req.message,
            history=history,
            conversation_id=req.conversation_id,
        ),
        media_type="text/plain; charset=utf-8",
    )
