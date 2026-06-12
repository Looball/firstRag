from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.repositories.conversation_repository import (
    create_conversation as create_conversation_record,
    get_user_conversations,
    rename_conversation as rename_conversation_record,
    soft_delete_conversation,
)
from app.schemas.conversation import (
    CreateConversationRequest,
    RenameConversationRequest,
)


router = APIRouter(prefix="/chat", tags=["conversations"])


# 加载当前用户全部会话
@router.get("/conversations")
def get_conversations(user_id: int = Depends(get_current_user_id)):
    """
    返回的数据结构：
    {
        "success": true,
        "conversations": [{
            "id": "会话UUID",
            "title": "会话标题",
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好，有什么可以帮你？"}
            ]
        }]
    }
    """
    # 查询数据
    rows = get_user_conversations(user_id)

    # 组建返回体消息
    conversations = {}
    for row in rows:
        # 获取会话id
        conversation_id = row["conversation_id"]

        # 第一次检查时创建会话结构
        if conversation_id not in conversations:
            conversations[conversation_id] = {
                "id": conversation_id,
                "title": row["title"],
                "created_at": row["conversation_created_at"],
                "updated_at": row["conversation_updated_at"],
                "messages": [],
            }

        # 将消息添加到"messages"
        if row["message_id"] is not None:
            conversations[conversation_id]["messages"].append({
                "id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["message_created_at"],
            })

    # 返回数据
    return {
        "success": True,
        "conversations": list(conversations.values()),
    }


# 会话重命名功能
@router.patch("/conversation/{conversation_id}")
def rename_conversation(
    conversation_id: UUID,
    req: RenameConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    # 更新数据库数据
    conversation = rename_conversation_record(
        conversation_id,
        user_id,
        req.title,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation": dict(conversation),
    }


# 软删除会话
@router.delete("/conversation/{conversation_id}")
def delete_conversation(
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    # 软删除
    conversation = soft_delete_conversation(conversation_id, user_id)
    # 会话是否存在
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation_id": str(conversation_id),
    }


# 新建会话
@router.post("/conversation")
def create_conversation(
    req: CreateConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    conversation = create_conversation_record(user_id, req.title)
    if conversation is None:
        raise HTTPException(status_code=500, detail="会话创建失败")

    return {
        "success": True,
        "message": "会话创建成功",
        "conversation": dict(conversation),
    }
