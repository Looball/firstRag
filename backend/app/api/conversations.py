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


def serialize_message_retrieval(row: dict) -> dict:
    """序列化历史消息检索状态，兼容旧消息。"""
    retrieval = row.get("retrieval") or {}
    sources = row.get("sources") or []
    if retrieval:
        return retrieval

    # 旧消息没有 retrieval 内容时，至少用 sources 数量恢复前端展示。
    if sources:
        return {
            "need_retrieval": True,
            "rewritten_query": "",
            "reason": "",
            "retrieved_count": len(sources),
            "source_count": len(sources),
        }

    return {}


def collect_source_retrieval_sources(sources: list[dict]) -> list[str]:
    """从引用来源中汇总实际使用过的检索通道。"""
    retrieval_sources = set()
    for source in sources:
        for retrieval_source in source.get("retrieval_sources") or []:
            retrieval_sources.add(str(retrieval_source))
    return sorted(retrieval_sources)


def serialize_source_preview(source: dict) -> dict:
    """序列化诊断接口中的引用预览，避免返回过多片段正文。"""
    return {
        "index": source.get("index"),
        "file_id": source.get("file_id"),
        "file_name": source.get("file_name"),
        "chunk_index": source.get("chunk_index"),
        "retrieval_sources": source.get("retrieval_sources") or [],
        "vector_score": source.get("vector_score"),
        "fulltext_score": source.get("fulltext_score"),
        "rrf_score": source.get("rrf_score"),
        "rerank_score": source.get("rerank_score"),
    }


def serialize_message_diagnostic(row: dict) -> dict:
    """序列化单条助手消息的 RAG 诊断信息。"""
    retrieval = serialize_message_retrieval(row)
    sources = row.get("sources") or []
    diagnostics = retrieval.get("diagnostics") or {}
    retrieval_sources = (
        retrieval.get("retrieval_sources")
        or diagnostics.get("retrieval_sources")
        or collect_source_retrieval_sources(sources)
    )

    return {
        "message_id": str(row["id"]),
        "status": row["status"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "need_retrieval": retrieval.get("need_retrieval"),
        "final_need_retrieval": retrieval.get(
            "final_need_retrieval",
            retrieval.get("need_retrieval"),
        ),
        "llm_need_retrieval": retrieval.get("llm_need_retrieval"),
        "rewritten_query": retrieval.get("rewritten_query", ""),
        "reason": retrieval.get("reason", ""),
        "llm_reason": retrieval.get("llm_reason", ""),
        "override_applied": bool(retrieval.get("override_applied", False)),
        "override_reason": retrieval.get("override_reason", ""),
        "retrieved_count": retrieval.get("retrieved_count", 0),
        "source_count": retrieval.get("source_count", len(sources)),
        "retrieval_sources": retrieval_sources,
        "vector_degraded": bool(
            retrieval.get("vector_degraded")
            or diagnostics.get("vector_degraded"),
        ),
        "diagnostics": diagnostics,
        "sources_preview": [
            serialize_source_preview(source)
            for source in sources
        ],
    }


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


@router.get("/conversations/{conversation_id}/diagnostics")
def get_conversation_diagnostics(
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """读取当前会话的 RAG 检索诊断信息。"""
    if not conversation_exists(user_id, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    rows = get_user_conversation_messages(user_id, conversation_id)
    assistant_rows = [
        row
        for row in rows
        if row["role"] == "assistant"
    ]
    return {
        "success": True,
        "conversation_id": str(conversation_id),
        "diagnostics": [
            serialize_message_diagnostic(row)
            for row in assistant_rows
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
                "retrieval": serialize_message_retrieval(row),
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
