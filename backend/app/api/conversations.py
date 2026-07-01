from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.repositories.conversation_repository import (
    conversation_belongs_base,
    conversation_exists,
    create_conversation as create_conversation_record,
    get_knowledge_base_conversations,
    get_user_conversations,
    rename_conversation as rename_conversation_record,
    soft_delete_conversation,
)
from app.repositories.knowledge_base_repository import (
    get_default_knowledge_base_id,
    knowledge_base_exists,
)
from app.repositories.message_feedback_repository import (
    find_message_source,
    get_quality_feedback_reasons,
    get_quality_feedback_summary,
    get_quality_irrelevant_source_files,
    get_quality_retrieval_summary,
    get_quality_source_summary,
    get_user_message_eval_draft_context,
    get_user_assistant_message,
    upsert_message_feedback,
    upsert_message_source_feedback,
)
from app.repositories.message_repository import get_user_conversation_messages
from app.schemas.conversation import (
    CreateConversationRequest,
    LegacyCreateConversationRequest,
    MessageFeedbackRequest,
    MessageSourceFeedbackRequest,
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


def serialize_conversation(row: dict) -> dict:
    """序列化会话记录为前端统一使用的响应结构。"""
    return {
        "id": str(row["id"]),
        "knowledge_base_id": str(row["knowledge_base_id"]),
        "title": row["title"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def coerce_optional_uuid(value: object) -> str | None:
    """把可选 UUID 字符串规范化；旧数据非法时返回 None。"""
    if not isinstance(value, str):
        return None

    try:
        return str(UUID(value))
    except ValueError:
        return None


def coerce_optional_int(value: object) -> int | None:
    """把可选整数值规范化；非法值返回 None。"""
    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip().isdigit():
        return int(value)

    return None


def coerce_float(value: object) -> float | None:
    """把数据库 numeric 结果转换为 JSON 友好的 float。"""
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ratio(numerator: int, denominator: int) -> float | None:
    """计算占比，分母为 0 时返回 None。"""
    if denominator <= 0:
        return None

    return numerator / denominator


def serialize_message_feedback(row: dict) -> dict | None:
    """序列化当前用户对消息的质量反馈。"""
    if not row.get("feedback_id"):
        return None

    return {
        "id": str(row["feedback_id"]),
        "rating": row["feedback_rating"],
        "reason": row["feedback_reason"],
        "note": row["feedback_note"],
        "metadata": row.get("feedback_metadata") or {},
        "created_at": row["feedback_created_at"],
        "updated_at": row["feedback_updated_at"],
    }


def serialize_source_feedback(feedback: dict) -> dict:
    """序列化当前用户对引用来源的反馈。"""
    return {
        "id": str(feedback["id"]),
        "source_index": feedback["source_index"],
        "knowledge_file_id": feedback.get("knowledge_file_id"),
        "chunk_index": feedback.get("chunk_index"),
        "rating": feedback["rating"],
        "note": feedback.get("note"),
        "metadata": feedback.get("metadata") or {},
        "created_at": feedback.get("created_at"),
        "updated_at": feedback.get("updated_at"),
    }


def build_eval_case_id(row: dict) -> str:
    """构造稳定且便于人工识别的 eval case 草稿 ID。"""
    message_id = str(row["message_id"])
    return f"draft_message_{message_id}"


def get_unique_source_file_names(sources: list[dict]) -> list[str]:
    """从 sources 中提取去重后的文件名，用作 eval expected_files 草稿。"""
    file_names: list[str] = []
    seen: set[str] = set()
    for source in sources:
        file_name = source.get("file_name") or source.get("title")
        if not isinstance(file_name, str) or not file_name.strip():
            continue
        normalized = file_name.strip()
        if normalized not in seen:
            seen.add(normalized)
            file_names.append(normalized)

    return file_names


def build_eval_case_draft(row: dict) -> dict:
    """把真实问答上下文转换为 RAG eval case 草稿。"""
    sources = row.get("sources") or []
    retrieval = row.get("retrieval") or {}
    expected_files = get_unique_source_file_names(sources)
    source_count = len(sources)
    need_retrieval = bool(
        retrieval.get("final_need_retrieval", retrieval.get("need_retrieval", source_count > 0)),
    )
    feedback = {
        "rating": row.get("feedback_rating"),
        "reason": row.get("feedback_reason"),
        "note": row.get("feedback_note"),
        "metadata": row.get("feedback_metadata") or {},
    }

    return {
        "id": build_eval_case_id(row),
        "knowledge_base_name": row.get("knowledge_base_name") or "默认知识库",
        "question": row.get("question") or "",
        "retrieval_settings": {
            "retrieval_mode": "auto",
            "enable_query_router": True,
            "enable_rerank": True,
        },
        "expect_retrieval": need_retrieval,
        "min_sources": 1 if source_count > 0 else 0,
        "expected_files": expected_files,
        "expected_keywords": [],
        "expected_reason_keywords": [],
        "expected_diagnostics": {},
        "draft_metadata": {
            "message_id": str(row["message_id"]),
            "question_message_id": (
                str(row["question_message_id"])
                if row.get("question_message_id") is not None
                else None
            ),
            "conversation_id": str(row["conversation_id"]),
            "conversation_title": row.get("conversation_title"),
            "knowledge_base_id": str(row["knowledge_base_id"]),
            "answer": row.get("answer") or "",
            "feedback": feedback,
            "retrieval": retrieval,
            "sources": sources,
        },
    }


def attach_source_feedbacks(row: dict) -> list[dict]:
    """把当前用户的 source feedback 附加到对应 sources 上。"""
    sources = [dict(source) for source in row.get("sources") or []]
    feedbacks = row.get("source_feedbacks") or []
    feedbacks_by_index = {
        feedback["source_index"]: serialize_source_feedback(feedback)
        for feedback in feedbacks
        if feedback.get("source_index") is not None
    }

    for position, source in enumerate(sources):
        source_index = source.get("index", position)
        feedback = feedbacks_by_index.get(source_index)
        if feedback:
            source["feedback"] = feedback

    return sources


@router.get("/quality-dashboard")
def get_quality_dashboard(
    days: int = 7,
    user_id: int = Depends(get_current_user_id),
):
    """读取当前用户的回答质量和检索表现看板摘要。"""
    normalized_days = min(max(days, 1), 90)
    feedback_summary = get_quality_feedback_summary(user_id, normalized_days) or {}
    reason_rows = get_quality_feedback_reasons(user_id, normalized_days)
    source_summary = get_quality_source_summary(user_id, normalized_days) or {}
    irrelevant_files = get_quality_irrelevant_source_files(
        user_id,
        normalized_days,
    )
    retrieval_summary = get_quality_retrieval_summary(user_id, normalized_days) or {}

    total_feedback = int(feedback_summary.get("total_feedback") or 0)
    positive_feedback = int(feedback_summary.get("positive_feedback") or 0)
    negative_feedback = int(feedback_summary.get("negative_feedback") or 0)
    total_source_feedback = int(source_summary.get("total_source_feedback") or 0)
    irrelevant_source_feedback = int(
        source_summary.get("irrelevant_source_feedback") or 0,
    )

    return {
        "success": True,
        "window_days": normalized_days,
        "has_feedback": total_feedback > 0 or total_source_feedback > 0,
        "message_feedback": {
            "total": total_feedback,
            "positive": positive_feedback,
            "negative": negative_feedback,
            "negative_rate": ratio(negative_feedback, total_feedback),
            "reason_distribution": [
                {
                    "reason": row["reason"],
                    "count": row["count"],
                }
                for row in reason_rows
            ],
        },
        "source_feedback": {
            "total": total_source_feedback,
            "useful": int(source_summary.get("useful_source_feedback") or 0),
            "irrelevant": irrelevant_source_feedback,
            "irrelevant_rate": ratio(
                irrelevant_source_feedback,
                total_source_feedback,
            ),
            "top_irrelevant_files": [
                {
                    "file_name": row["file_name"],
                    "count": row["count"],
                }
                for row in irrelevant_files
            ],
        },
        "retrieval": {
            "assistant_messages": int(
                retrieval_summary.get("assistant_messages") or 0,
            ),
            "average_sources": coerce_float(
                retrieval_summary.get("average_sources"),
            ),
            "average_first_token_ms": coerce_float(
                retrieval_summary.get("average_first_token_ms"),
            ),
        },
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


@router.get("/conversations")
def get_all_conversations(user_id: int = Depends(get_current_user_id)):
    """读取当前用户所有知识库下的会话，用于兼容旧前端代理。"""
    rows = get_user_conversations(user_id)
    return {
        "success": True,
        "conversations": [
            serialize_conversation(row)
            for row in rows
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


@router.post("/conversation")
def create_conversation_legacy(
    req: LegacyCreateConversationRequest | None = None,
    user_id: int = Depends(get_current_user_id),
):
    """兼容旧前端代理创建会话，未传知识库时使用当前用户默认知识库。"""
    knowledge_base_id = (
        req.knowledge_base_id
        if req is not None and req.knowledge_base_id is not None
        else get_default_knowledge_base_id(user_id)
    )
    if knowledge_base_id is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if not knowledge_base_exists(knowledge_base_id, user_id):
        raise HTTPException(status_code=404, detail="知识库不存在")

    conversation = create_conversation_record(
        user_id,
        knowledge_base_id,
        req.title if req is not None else "新会话",
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return {
        "success": True,
        "message": "会话创建成功",
        "conversation": serialize_conversation(conversation),
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


@router.patch("/conversation/{conversation_id}")
def rename_conversation_legacy(
    conversation_id: UUID,
    req: RenameConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    """兼容旧前端代理按会话 ID 重命名会话。"""
    if not conversation_exists(user_id, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    conversation = rename_conversation_record(
        conversation_id,
        user_id,
        req.title,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation": serialize_conversation(conversation),
    }


@router.delete("/conversation/{conversation_id}")
def delete_conversation_legacy(
    conversation_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    """兼容旧前端代理按会话 ID 软删除会话。"""
    conversation = soft_delete_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "conversation_id": str(conversation_id),
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
                "sources": attach_source_feedbacks(row),
                "retrieval": serialize_message_retrieval(row),
                "feedback": serialize_message_feedback(row),
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }


@router.post("/messages/{message_id}/sources/{source_index}/feedback")
def submit_message_source_feedback(
    message_id: int,
    source_index: int,
    req: MessageSourceFeedbackRequest,
    user_id: int = Depends(get_current_user_id),
):
    """提交或更新当前用户对助手消息单个引用来源的反馈。"""
    message = get_user_assistant_message(user_id, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="消息不存在")

    source_match = find_message_source(message.get("sources") or [], source_index)
    if source_match is None:
        raise HTTPException(status_code=404, detail="引用来源不存在")

    _, source = source_match
    persisted_source_index = coerce_optional_int(
        source.get("index"),
    )
    if persisted_source_index is None:
        persisted_source_index = source_index
    feedback = upsert_message_source_feedback(
        user_id=user_id,
        message_id=message_id,
        source_index=persisted_source_index,
        knowledge_file_id=coerce_optional_uuid(
            source.get("file_id") or source.get("knowledge_file_id"),
        ),
        chunk_index=coerce_optional_int(source.get("chunk_index")),
        rating=req.rating,
        note=req.note.strip() if req.note else None,
        metadata={
            "file_name": source.get("file_name"),
            "retrieval_sources": source.get("retrieval_sources") or [],
        },
    )
    if feedback is None:
        raise HTTPException(status_code=500, detail="保存引用反馈失败")

    return {
        "success": True,
        "feedback": serialize_source_feedback(feedback),
    }


@router.get("/messages/{message_id}/eval-case-draft")
def export_message_eval_case_draft(
    message_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """导出当前用户真实问答对应的 RAG eval case 草稿。"""
    row = get_user_message_eval_draft_context(user_id, message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    if not row.get("question"):
        raise HTTPException(status_code=400, detail="缺少可导出的用户问题")

    return {
        "success": True,
        "draft": build_eval_case_draft(row),
    }


@router.post("/messages/{message_id}/feedback")
def submit_message_feedback(
    message_id: int,
    req: MessageFeedbackRequest,
    user_id: int = Depends(get_current_user_id),
):
    """提交或更新当前用户对助手消息的质量反馈。"""
    message = get_user_assistant_message(user_id, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="消息不存在")

    feedback = upsert_message_feedback(
        user_id=user_id,
        message_id=message_id,
        rating=req.rating,
        reason=req.reason,
        note=req.note.strip() if req.note else None,
        metadata={"status": message["status"]},
    )
    if feedback is None:
        raise HTTPException(status_code=500, detail="保存反馈失败")

    return {
        "success": True,
        "feedback": {
            "id": str(feedback["id"]),
            "message_id": str(feedback["message_id"]),
            "rating": feedback["rating"],
            "reason": feedback["reason"],
            "note": feedback["note"],
            "metadata": feedback.get("metadata") or {},
            "created_at": feedback["created_at"],
            "updated_at": feedback["updated_at"],
        },
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
