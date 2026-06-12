from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    load_chat_history,
    save_message,
    stream_answer_and_save,
)
from app.services.rag_service import get_chain
from SqlStatement.query import exe_sql


router = APIRouter(tags=["chat"])


# 请求聊天接口
@router.post("/chat")
def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
) -> StreamingResponse:
    # 取出请求体中的数据并检查消息内容
    if not req.message:
        raise HTTPException(status_code=400, detail="message不能为空")

    # 检查会话存在且属于当前用户
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

    # 取出历史记录
    history = load_chat_history(req.conversation_id)

    # 保存用户输入
    save_message(req.conversation_id, "user", req.message)

    # 创建检索链
    chain = get_chain()

    # 返回流式响应
    return StreamingResponse(
        stream_answer_and_save(
            chain=chain,
            user_input=req.message,
            history=history,
            conversation_id=req.conversation_id,
        ),
        media_type="text/plain; charset=utf-8",
    )
