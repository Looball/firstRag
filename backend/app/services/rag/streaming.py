from collections.abc import Iterator
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableSerializable

from app.services.knowledge_profile_cache import (
    reset_knowledge_profile_cache_diagnostics,
)
from app.services.rag.diagnostics import (
    elapsed_ms,
    extract_answer_text,
    extract_token_usage_from_chunk,
    merge_diagnostics_timing,
    merge_knowledge_profile_cache_diagnostics,
    merge_llm_token_usage,
    merge_retrieval_settings_diagnostics,
    reset_retrieval_settings_diagnostics,
    extract_retrieval_settings_diagnostics,
)
from app.services.rag.reference_serializer import serialize_reference_documents
from app.services.rag.retrieval_decision import normalize_retrieval_decision
from app.services.rag.retrieval_pipeline import (
    extract_retrieval_diagnostics_from_docs,
)
from app.services.rag.types import RagStreamEvent, RetrievalDecision
from app.services.retrieval.hybrid_retriever import get_retrieval_diagnostics
from app.services.retrieval_settings_cache import (
    reset_retrieval_settings_cache_diagnostics,
)

RAG_STAGE_TIMING_FIELDS = {
    "standalone_question": "standalone_question",
    "retrieval_settings": "retrieval_settings",
    "knowledge_profile": "knowledge_profile",
    "raw_retrieval_decision": "query_router",
    "retrieval_decision": "finalize_decision",
    "context": "retrieve_documents",
}

def get_answer(
    chain: RunnableSerializable,
    user_input: str,
    chat_history: list,
    user_id: int,
    knowledge_base_id: UUID,
) -> Iterator[str]:
    """流式返回 LCEL 链生成的答案。"""
    for event in stream_rag_response(
        chain=chain,
        user_input=user_input,
        chat_history=chat_history,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    ):
        if event["type"] == "answer":
            yield event["content"]


def stream_rag_response(
    chain: RunnableSerializable,
    user_input: str,
    chat_history: list,
    user_id: int,
    knowledge_base_id: UUID,
) -> Iterator[RagStreamEvent]:
    """流式返回 RAG 事件，包括引用文档和答案片段。"""
    reset_knowledge_profile_cache_diagnostics()
    reset_retrieval_settings_diagnostics()
    reset_retrieval_settings_cache_diagnostics()
    stream_started_at = perf_counter()
    current_stage_started_at = stream_started_at
    rag_timing: dict[str, float] = {}

    def record_rag_stage(stage: str) -> None:
        """记录 LCEL 流式阶段耗时和相对起点耗时。"""
        nonlocal current_stage_started_at
        if f"{stage}_ms" in rag_timing:
            return

        now = perf_counter()
        rag_timing[f"{stage}_ms"] = round(
            (now - current_stage_started_at) * 1000,
            2,
        )
        rag_timing[f"{stage}_elapsed_ms"] = round(
            (now - stream_started_at) * 1000,
            2,
        )
        current_stage_started_at = now

    response = chain.stream({
        "input": user_input,
        "chat_history": chat_history,
        "user_id": user_id,
        "knowledge_base_id": knowledge_base_id,
    })

    sources_sent = False
    retrieval_sent = False
    retrieval_decision: RetrievalDecision | None = None
    retrieval_settings_diagnostics: dict[str, Any] | None = None
    llm_diagnostics: dict[str, Any] | None = None
    first_answer_token_recorded = False
    for chunk in response:
        for chunk_key, stage in RAG_STAGE_TIMING_FIELDS.items():
            if chunk_key in chunk:
                record_rag_stage(stage)

        if isinstance(chunk.get("llm_diagnostics"), dict):
            llm_diagnostics = chunk["llm_diagnostics"]

        if isinstance(chunk.get("retrieval_settings"), dict):
            retrieval_settings_diagnostics = (
                extract_retrieval_settings_diagnostics(
                    chunk["retrieval_settings"],
                )
            )

        if "retrieval_decision" in chunk:
            retrieval_decision = normalize_retrieval_decision(
                chunk["retrieval_decision"],
            )

        if "context" in chunk and not sources_sent:
            context = chunk["context"] or []
            sources = serialize_reference_documents(
                context,
                user_id=user_id,
            )
            diagnostics = (
                extract_retrieval_diagnostics_from_docs(context)
                or get_retrieval_diagnostics()
            )
            rag_timing["pre_answer_total_ms"] = elapsed_ms(stream_started_at)
            diagnostics_with_timing = merge_diagnostics_timing(
                diagnostics,
                rag_timing,
                llm_diagnostics,
            )
            diagnostics_with_timing = merge_retrieval_settings_diagnostics(
                diagnostics_with_timing,
                retrieval_settings_diagnostics,
            )
            diagnostics_with_timing = merge_knowledge_profile_cache_diagnostics(
                diagnostics_with_timing,
            )
            if not retrieval_sent:
                decision = normalize_retrieval_decision(retrieval_decision)
                retrieval_event = {
                    "type": "retrieval",
                    "need_retrieval": decision["need_retrieval"],
                    "final_need_retrieval": decision["final_need_retrieval"],
                    "llm_need_retrieval": decision["llm_need_retrieval"],
                    "rewritten_query": decision["rewritten_query"],
                    "reason": decision["reason"],
                    "llm_reason": decision["llm_reason"],
                    "override_applied": decision["override_applied"],
                    "override_reason": decision["override_reason"],
                    "retrieved_count": len(context),
                    "source_count": len(sources),
                }
                retrieval_event["diagnostics"] = diagnostics_with_timing
                retrieval_event["retrieval_sources"] = (
                    diagnostics_with_timing.get("retrieval_sources") or []
                )
                retrieval_event["vector_degraded"] = bool(
                    diagnostics_with_timing.get("vector_degraded"),
                )
                yield retrieval_event
                retrieval_sent = True

            # 没有可信引用时不发送 sources 事件，避免前端展示空 Sources。
            if sources:
                yield {
                    "type": "sources",
                    "sources": sources,
                }
            sources_sent = True

        if "answer" in chunk:
            answer_chunk = chunk["answer"]
            token_usage = extract_token_usage_from_chunk(answer_chunk)
            if token_usage:
                llm_diagnostics = merge_llm_token_usage(
                    llm_diagnostics,
                    token_usage,
                )
                yield {
                    "type": "llm_usage",
                    "llm": llm_diagnostics,
                }

            content = extract_answer_text(answer_chunk)
            if not content:
                continue

            if not first_answer_token_recorded:
                rag_timing["first_answer_token_ms"] = elapsed_ms(
                    stream_started_at,
                )
                first_answer_token_recorded = True
            yield {
                "type": "answer",
                "content": content,
            }
