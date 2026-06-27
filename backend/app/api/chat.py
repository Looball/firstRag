from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user_id
from app.repositories.conversation_repository import (
    conversation_belongs_base,
    conversation_exists,
)
from app.repositories.retrieval_settings_repository import (
    DEFAULT_RETRIEVAL_SETTINGS,
    get_knowledge_base_retrieval_settings,
)
from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    get_local_chat_response,
    load_chat_history,
    save_message,
    stream_answer_and_save,
    stream_local_answer_and_save,
)
from app.services.rag_service import get_chain


router = APIRouter(tags=["chat"])


def should_use_local_chat_response(
    user_id: int,
    knowledge_base_id: UUID,
) -> bool:
    """判断当前知识库设置是否允许本地问候短路。"""
    settings = get_knowledge_base_retrieval_settings(
        knowledge_base_id=knowledge_base_id,
        user_id=user_id,
    ) or DEFAULT_RETRIEVAL_SETTINGS
    retrieval_mode = settings.get("retrieval_mode", "auto")

    if retrieval_mode == "always":
        return False

    if (
        retrieval_mode == "auto"
        and settings.get("enable_query_router") is False
    ):
        return False

    return True


# 请求聊天接口
@router.post("/chat")
def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
) -> StreamingResponse:
    # 取出请求体中的数据并检查消息内容
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message不能为空")

    # 检查会话存在且属于当前用户
    if not conversation_exists(user_id, req.conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    # 检查会话是否属于当前知识库
    if not conversation_belongs_base(user_id, req.knowledge_base_id, req.conversation_id):
        raise HTTPException(status_code=404, detail="禁止跨知识库提问")

    local_answer = get_local_chat_response(req.message)
    if local_answer is not None and not should_use_local_chat_response(
        user_id,
        req.knowledge_base_id,
    ):
        local_answer = None
    if local_answer is not None:
        # 本地可确定的问候类消息不需要构建 RAG 链，避免额外模型调用。
        save_message(req.conversation_id, "user", req.message)
        assistant_message = save_message(
            req.conversation_id,
            "assistant",
            "",
            status="generating",
        )
        return StreamingResponse(
            stream_local_answer_and_save(
                local_answer,
                assistant_message["id"],
            ),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # 取出历史记录
    history = load_chat_history(req.conversation_id)

    # 先验证模型配置；失败时不写入本轮消息，避免产生孤立记录。
    try:
        chain = get_chain(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"模型配置无效：{exc}",
        ) from exc

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
