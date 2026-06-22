from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.repositories.conversation_repository import conversation_exists,conversation_belongs_base
from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    load_chat_history,
    save_message,
    stream_answer_and_save,
)
from app.services.rag_service import get_chain


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
    if not conversation_exists(user_id, req.conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    # 检查会话是否属于当前知识库
    if not conversation_belongs_base(user_id, req.knowledge_base_id, req.conversation_id):
        raise HTTPException(status_code=404, detail="禁止跨知识库提问")

    # 取出历史记录
    history = load_chat_history(req.conversation_id)

    # 创建检索链
    chain = get_chain(user_id)

    # 创建链成功后再持久化本轮消息，避免配置错误留下孤立用户消息。
    save_message(req.conversation_id, "user", req.message)
    assistant_message = save_message(
        req.conversation_id,
        "assistant",
        "",
        status="generating",
    )

    # 返回流式响应
    return StreamingResponse(
        stream_answer_and_save(
            chain=chain,
            user_input=req.message,
            history=history,
            conversation_id=req.conversation_id,
            assistant_message_id=assistant_message["id"],
            user_id=user_id,
            knowledge_base_id=req.knowledge_base_id,
        ),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
