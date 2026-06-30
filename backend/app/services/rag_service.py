from langchain_openai import ChatOpenAI

from app.services.llm_service import create_openai_compatible_chat_model
from app.services.rag.chain_builder import get_chain
from app.services.rag.diagnostics import (
    RETRIEVAL_SETTINGS_DIAGNOSTICS_KEY,
    elapsed_ms,
    extract_answer_text,
    extract_retrieval_settings_diagnostics,
    extract_token_usage_from_chunk,
    get_retrieval_settings_diagnostics,
    merge_diagnostics_timing,
    merge_knowledge_profile_cache_diagnostics,
    merge_llm_token_usage,
    merge_retrieval_settings_diagnostics,
    normalize_token_usage_value,
    reset_retrieval_settings_diagnostics,
    serialize_llm_diagnostics,
)
from app.services.rag.reference_serializer import (
    REFERENCE_RERANK_SCORE_THRESHOLD,
    filter_relevant_reference_documents,
    get_reference_threshold_from_docs,
    get_res_doc,
    is_reference_document_relevant,
    serialize_reference_documents,
)
from app.services.rag.retrieval_decision import (
    append_reason_once,
    build_configured_retrieval_decision,
    build_ngrams_from_chars,
    extract_chinese_ngrams,
    finalize_retrieval_decision,
    format_route_info,
    normalize_retrieval_decision,
    normalize_retrieval_settings,
    parse_retrieval_decision,
    should_force_retrieval_by_profile,
    should_run_query_router,
)
from app.services.rag.retrieval_pipeline import (
    build_knowledge_base_profile,
    extract_retrieval_diagnostics_from_docs,
    get_hybrid_documents,
    get_knowledge_base_file_ids,
    get_knowledge_base_files,
    get_knowledge_base_retrieval_settings,
    get_retrieval_diagnostics,
    load_retrieval_settings,
    retrieve_documents,
)
from app.services.rag.streaming import get_answer, stream_rag_response
from app.services.rag.types import (
    ChainInput,
    RagStreamEvent,
    RetrievalDecision,
    RetrievedDocs,
)
from app.services.knowledge_profile_cache import (
    get_knowledge_profile_cache_diagnostics,
)
from app.services.user_settings_service import (
    get_effective_chat_model_config,
    get_effective_chat_model_settings,
)


def create_chat_model(user_id: int) -> ChatOpenAI:
    """创建当前用户生效的 OpenAI 兼容聊天模型。"""
    settings = get_effective_chat_model_settings(user_id)
    return create_openai_compatible_chat_model(settings)
