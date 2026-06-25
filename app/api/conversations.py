from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.repositories.conversation_repository import (
    conversation_belongs_base,
    conversation_exists,
    create_conversation as create_conversation_record,
    get_knowledge_base_conversations,
    rename_conversation as rename_conversation_record,
    soft_delete_conversation,
)
from app.repositories.knowledge_base_repository import knowledge_base_exists
from app.repositories.message_repository import get_user_conversation_messages
from app.schemas.conversation import (
    CreateConversationRequest,
    RenameConversationRequest,
)


router = APIRouter(prefix="/chat", tags=["conversations"])


# 加载当前用户指定知识库下的会话
@router.get("/knowledge-bases/{knowledge_base_id}/conversations")
def get_conversations(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """
    返回的数据结构：
    {
        "success": true,
        "conversations": [{
            "id": "会话UUID",
            "knowledge_base_id": "知识库UUID",
            "title": "会话标题",
        }]
    }
    """
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    rows = get_knowledge_base_conversations(user_id, knowledge_base_id)
    return {
        "success": True,
        "conversations": [
            {
                "id": str(row["conversation_id"]),
                "knowledge_base_id": str(row["knowledge_base_id"]),
                "title": row["title"],
                "created_at": row["conversation_created_at"],
                "updated_at": row["conversation_updated_at"],
            }
            for row in rows
        ],
    }


# 加载当前用户指定会话下的消息
@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    if not conversation_exists(user_id, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    rows = get_user_conversation_messages(user_id, conversation_id)
    return {
        "success": True,
        "conversation_id": str(conversation_id),
        "messages": [
            {
                "id": str(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "status": row["status"],
                "error_message": row["error_message"],
                "sources": row["sources"] or [],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }


# 会话重命名功能
@router.patch("/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}")
def rename_conversation(
    knowledge_base_id: UUID,
    conversation_id: UUID,
    req: RenameConversationRequest,
    user_id: int = Depends(get_current_user_id),
):

    # 检查当前知识库是否存在当前会话
    if not conversation_belongs_base(user_id, knowledge_base_id, conversation_id):
        raise HTTPException(status_code=404, detail="禁止跨知识库提问")

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
@router.delete("/knowledge-bases/{knowledge_base_id}/conversations/{conversation_id}")
def delete_conversation(
    knowledge_base_id: UUID,
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):

    # 检查当前知识库是否存在当前会话
    if not conversation_belongs_base(user_id, knowledge_base_id, conversation_id):
        raise HTTPException(status_code=404, detail="禁止跨知识库提问")

    # 软删除
    conversation = soft_delete_conversation(conversation_id, user_id)
    # 判断是否删除成功
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation_id": str(conversation_id),
    }


# 新建会话
@router.post("/knowledge-bases/{knowledge_base_id}/conversations")
def create_conversation(
    knowledge_base_id: UUID,
    req: CreateConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    """在当前用户的知识库中创建会话。"""
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    conversation = create_conversation_record(user_id, knowledge_base_id, req.title)
    if conversation is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return {
        "success": True,
        "message": "会话创建成功",
        "conversation": dict(conversation),
    }
