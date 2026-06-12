from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.schemas.conversation import (
    CreateConversationRequest,
    RenameConversationRequest,
)
from SqlStatement.query import exe_sql


router = APIRouter(prefix="/chat", tags=["conversations"])


@router.get("/conversations")
def get_conversations(user_id: int = Depends(get_current_user_id)):
    rows = exe_sql(
        sql_statement="""
        SELECT
            c.id AS conversation_id,
            c.title,
            c.created_at AS conversation_created_at,
            c.updated_at AS conversation_updated_at,
            m.id AS message_id,
            m.role,
            m.content,
            m.created_at AS message_created_at
        FROM conversations AS c
        LEFT JOIN messages AS m
          ON m.conversation_id = c.id
        WHERE c.user_id = %s
          AND c.deleted_at IS NULL
        ORDER BY c.updated_at DESC, m.created_at ASC, m.id ASC;
        """,
        args_tuple=(user_id,),
    )

    conversations = {}
    for row in rows:
        conversation_id = row["conversation_id"]
        if conversation_id not in conversations:
            conversations[conversation_id] = {
                "id": conversation_id,
                "title": row["title"],
                "created_at": row["conversation_created_at"],
                "updated_at": row["conversation_updated_at"],
                "messages": [],
            }

        if row["message_id"] is not None:
            conversations[conversation_id]["messages"].append({
                "id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["message_created_at"],
            })

    return {
        "success": True,
        "conversations": list(conversations.values()),
    }


@router.patch("/conversation/{conversation_id}")
def rename_conversation(
    conversation_id: UUID,
    req: RenameConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    rows = exe_sql(
        sql_statement="""
        UPDATE conversations
        SET title = %s,
            updated_at = now()
        WHERE id = %s AND user_id = %s
        RETURNING id, user_id, title, created_at, updated_at;
        """,
        args_tuple=(req.title, conversation_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation": dict(rows[0]),
    }


@router.delete("/conversation/{conversation_id}")
def delete_conversation(
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    rows = exe_sql(
        sql_statement="""
        UPDATE conversations
        SET deleted_at = now(),
            updated_at = now()
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        RETURNING id;
        """,
        args_tuple=(conversation_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation_id": str(conversation_id),
    }


@router.post("/conversation")
def create_conversation(
    req: CreateConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    rows = exe_sql(
        sql_statement="""
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, user_id, title, created_at, updated_at;
        """,
        args_tuple=(user_id, req.title),
    )
    return {
        "success": True,
        "message": "会话创建成功",
        "conversation": dict(rows[0]),
    }
