import json
from collections.abc import Iterator
from time import perf_counter
from typing import Any, cast
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnablePassthrough,
    RunnableSerializable,
)
from langchain_openai import ChatOpenAI

from app.repositories.knowledge_base_repository import (
    get_knowledge_base_files,
)
from app.repositories.retrieval_settings_repository import (
    DEFAULT_RETRIEVAL_SETTINGS,
    get_knowledge_base_retrieval_settings,
)
from app.services.user_settings_service import (
    get_effective_chat_model_config,
    get_effective_chat_model_settings,
)
from app.services.llm_service import (
    ChatModelSettings,
    create_openai_compatible_chat_model,
    resolve_base_url,
)
from app.services.retrieval.hybrid_retriever import (
    get_hybrid_documents,
    get_retrieval_diagnostics,
)
from app.services.knowledge_profile_cache import (
    get_cached_knowledge_base_context,
    get_knowledge_profile_cache_diagnostics,
    reset_knowledge_profile_cache_diagnostics,
)


type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]
type RagStreamEvent = dict[str, Any]
type RetrievalDecision = dict[str, Any]


REFERENCE_RERANK_SCORE_THRESHOLD = 0.0
MAX_KNOWLEDGE_PROFILE_FILES = 30
RAG_STAGE_TIMING_FIELDS = {
    "standalone_question": "standalone_question",
    "retrieval_settings": "retrieval_settings",
    "knowledge_profile": "knowledge_profile",
    "raw_retrieval_decision": "query_router",
    "retrieval_decision": "finalize_decision",
    "context": "retrieve_documents",
}


def elapsed_ms(started_at: float) -> float:
    """计算从指定时间点到当前的毫秒耗时。"""
    return round((perf_counter() - started_at) * 1000, 2)


def merge_diagnostics_timing(
    diagnostics: dict[str, Any] | None,
    timing: dict[str, float],
    llm_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 RAG 外层耗时合并进 retrieval diagnostics。"""
    merged = dict(diagnostics or {})
    existing_timing = merged.get("timing")
    if not isinstance(existing_timing, dict):
        existing_timing = {}
    merged["timing"] = {
        **existing_timing,
        **timing,
    }
    if llm_diagnostics is not None:
        merged["llm"] = llm_diagnostics
    return merged


def create_chat_model(user_id: int) -> ChatOpenAI:
    """创建当前用户生效的 OpenAI 兼容聊天模型。"""
    settings = get_effective_chat_model_settings(user_id)
    return create_openai_compatible_chat_model(settings)


def serialize_llm_diagnostics(
    settings: ChatModelSettings,
    credential_mode: str,
) -> dict[str, Any]:
    """生成不含 API Key 的 LLM 调用诊断信息。"""
    return {
        "provider": settings.provider,
        "model": settings.model,
        "credential_mode": credential_mode,
        "base_url": resolve_base_url(settings.provider, settings.base_url),
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def normalize_token_usage_value(value: Any) -> int | None:
    """将模型返回的 token usage 值规范化为整数或 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def extract_token_usage_from_chunk(chunk: Any) -> dict[str, int | None]:
    """从 LangChain/OpenAI 流式消息块中提取 token usage。"""
    usage = getattr(chunk, "usage_metadata", None)
    if not isinstance(usage, dict):
        response_metadata = getattr(chunk, "response_metadata", None)
        if isinstance(response_metadata, dict):
            usage = (
                response_metadata.get("token_usage")
                or response_metadata.get("usage")
            )
    if not isinstance(usage, dict):
        additional_kwargs = getattr(chunk, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            usage = (
                additional_kwargs.get("token_usage")
                or additional_kwargs.get("usage")
            )

    if not isinstance(usage, dict):
        return {}

    prompt_tokens = (
        usage.get("prompt_tokens")
        if "prompt_tokens" in usage
        else usage.get("input_tokens")
    )
    completion_tokens = (
        usage.get("completion_tokens")
        if "completion_tokens" in usage
        else usage.get("output_tokens")
    )
    total_tokens = usage.get("total_tokens")

    return {
        "prompt_tokens": normalize_token_usage_value(prompt_tokens),
        "completion_tokens": normalize_token_usage_value(completion_tokens),
        "total_tokens": normalize_token_usage_value(total_tokens),
    }


def merge_llm_token_usage(
    llm_diagnostics: dict[str, Any] | None,
    token_usage: dict[str, int | None],
) -> dict[str, Any] | None:
    """把 token usage 合并到 LLM 诊断信息中。"""
    if llm_diagnostics is None or not token_usage:
        return llm_diagnostics

    merged = dict(llm_diagnostics)
    for key, value in token_usage.items():
        if value is not None:
            merged[key] = value
    return merged


def extract_answer_text(chunk: Any) -> str:
    """从模型流式 chunk 中提取可返回给前端的文本内容。"""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def is_reference_document_relevant(
    doc: Document,
    rerank_score_threshold: float = REFERENCE_RERANK_SCORE_THRESHOLD,
) -> bool:
    """判断检索片段是否足够可信，可以进入上下文和前端引用。

    BGE Cross-Encoder reranker 输出 raw logits，分数越大越相关。
    当前混合检索默认启用 reranker，因此低于 0 的片段通常是弱相关或
    误召回片段，不应在用户只问“你好”这类问题时展示成来源。
    如果历史数据或降级路径没有 rerank_score，则保持兼容，暂不拦截。
    """
    score = doc.metadata.get("rerank_score")
    if score is None:
        return True

    try:
        return float(score) >= rerank_score_threshold
    except (TypeError, ValueError):
        return True


def filter_relevant_reference_documents(
    docs: list[Document],
    rerank_score_threshold: float = REFERENCE_RERANK_SCORE_THRESHOLD,
) -> list[Document]:
    """过滤掉低相关检索片段，避免误展示 Sources。"""
    return [
        doc
        for doc in docs
        if isinstance(doc, Document)
        and is_reference_document_relevant(doc, rerank_score_threshold)
    ]


def get_reference_threshold_from_docs(docs: list[Document]) -> float:
    """从文档 metadata 读取本轮引用展示阈值，缺失时使用默认值。"""
    for doc in docs:
        if not isinstance(doc, Document):
            continue
        threshold = doc.metadata.get("rerank_score_threshold")
        try:
            return float(threshold)
        except (TypeError, ValueError):
            continue

    return REFERENCE_RERANK_SCORE_THRESHOLD


def normalize_retrieval_settings(settings: dict[str, Any] | None) -> dict:
    """规范化知识库检索设置，保证链路内部总能拿到完整字段。"""
    normalized = dict(DEFAULT_RETRIEVAL_SETTINGS)
    if isinstance(settings, dict):
        normalized.update({
            key: value
            for key, value in settings.items()
            if value is not None and key in DEFAULT_RETRIEVAL_SETTINGS
        })
    return normalized


def load_retrieval_settings(inputs: ChainInput) -> dict:
    """读取当前知识库的检索设置，未配置时使用默认值。"""
    settings = get_knowledge_base_retrieval_settings(
        knowledge_base_id=inputs["knowledge_base_id"],
        user_id=inputs["user_id"],
    )
    return normalize_retrieval_settings(settings)


def should_run_query_router(inputs: ChainInput) -> bool:
    """判断本轮是否需要调用 Router LLM。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    return (
        settings["retrieval_mode"] == "auto"
        and bool(settings["enable_query_router"])
    )


def build_configured_retrieval_decision(inputs: ChainInput) -> RetrievalDecision:
    """当配置跳过 Router LLM 时，生成确定性的路由结果。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    query = str(inputs.get("standalone_question") or inputs.get("input") or "")
    mode = settings["retrieval_mode"]

    if mode == "never":
        return {
            "need_retrieval": False,
            "rewritten_query": query,
            "reason": "当前知识库设置为永不检索",
        }

    if mode == "always":
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": "当前知识库设置为强制检索",
        }

    return {
        "need_retrieval": True,
        "rewritten_query": query,
        "reason": "Query Router 已关闭，默认执行知识库检索",
    }


def append_reason_once(reason: str, suffix: str) -> str:
    """向路由原因追加说明，避免相同配置原因重复出现。"""
    if suffix in reason:
        return reason
    return f"{reason}；{suffix}" if reason else suffix


def normalize_retrieval_decision(
    decision: dict[str, Any] | None,
) -> RetrievalDecision:
    """规范化检索路由结果，异常或缺失时保守选择检索。"""
    if not isinstance(decision, dict):
        return {
            "need_retrieval": True,
            "final_need_retrieval": True,
            "llm_need_retrieval": None,
            "rewritten_query": "",
            "reason": "路由结果无效，保守执行知识库检索",
            "llm_reason": "路由结果无效",
            "override_applied": True,
            "override_reason": "路由结果无效，保守执行知识库检索",
        }

    need_retrieval = decision.get("need_retrieval", True)
    if isinstance(need_retrieval, str):
        need_retrieval = need_retrieval.strip().lower()
        need_retrieval = need_retrieval not in {"false", "0", "no", "否"}
    rewritten_query = str(decision.get("rewritten_query") or "").strip()
    reason = str(decision.get("reason") or "").strip()

    normalized: RetrievalDecision = {
        "need_retrieval": bool(need_retrieval),
        "final_need_retrieval": bool(need_retrieval),
        "rewritten_query": rewritten_query,
        "reason": reason or "未提供原因",
        "llm_reason": str(
            decision.get("llm_reason") or reason or "未提供原因",
        ).strip(),
        "override_applied": bool(decision.get("override_applied", False)),
        "override_reason": str(decision.get("override_reason") or "").strip(),
    }

    llm_need_retrieval = decision.get("llm_need_retrieval")
    if isinstance(llm_need_retrieval, bool):
        normalized["llm_need_retrieval"] = llm_need_retrieval
    elif "llm_need_retrieval" not in decision:
        normalized["llm_need_retrieval"] = bool(need_retrieval)
    else:
        normalized["llm_need_retrieval"] = None

    final_need_retrieval = decision.get("final_need_retrieval")
    if isinstance(final_need_retrieval, bool):
        normalized["final_need_retrieval"] = final_need_retrieval
        normalized["need_retrieval"] = final_need_retrieval

    return normalized


def parse_retrieval_decision(raw_output: str) -> RetrievalDecision:
    """解析 Router LLM 输出的 JSON 路由结果。

    Router 可能因为模型格式漂移输出 Markdown 代码块或额外说明。
    这里尽量抽取第一段 JSON；解析失败时保守走检索，避免知识库问题被误判。
    """
    text = raw_output.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start >= 0 and json_end >= json_start:
        text = text[json_start:json_end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return normalize_retrieval_decision(None)

    return normalize_retrieval_decision(parsed)


def extract_chinese_ngrams(text: str, min_size: int = 2, max_size: int = 6) -> set[str]:
    """提取中文 ngram，用于判断问题和知识库画像是否有主题重合。"""
    terms: set[str] = set()
    buffer = []
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            buffer.append(char)
            continue

        if buffer:
            terms.update(build_ngrams_from_chars(buffer, min_size, max_size))
            buffer.clear()

    if buffer:
        terms.update(build_ngrams_from_chars(buffer, min_size, max_size))

    return terms


def build_ngrams_from_chars(
    chars: list[str],
    min_size: int,
    max_size: int,
) -> set[str]:
    """从连续中文字符中生成 ngram 集合。"""
    terms: set[str] = set()
    length = len(chars)
    for size in range(min_size, min(max_size, length) + 1):
        for start in range(0, length - size + 1):
            terms.add("".join(chars[start:start + size]))
    return terms


def should_force_retrieval_by_profile(question: str, profile: str) -> bool:
    """当问题关键词命中知识库文件画像时，强制走检索。

    Router 对“什么是诉讼法”这类问题可能判断成通用问答。但如果当前
    知识库文件名里有“民事诉讼法”，用户通常期待基于知识库回答并展示引用。
    因此这里用轻量 ngram 重合做确定性兜底。
    """
    question_terms = extract_chinese_ngrams(question)
    if not question_terms:
        return False

    profile_terms = extract_chinese_ngrams(profile)
    return bool(question_terms & profile_terms)


def finalize_retrieval_decision(inputs: ChainInput) -> RetrievalDecision:
    """结合 Router 结果和知识库画像生成最终检索决策。"""
    decision = normalize_retrieval_decision(
        inputs.get("raw_retrieval_decision"),
    )
    query = decision["rewritten_query"] or inputs.get(
        "standalone_question",
        "",
    )
    profile = str(inputs.get("knowledge_profile") or "")
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    retrieval_mode = settings["retrieval_mode"]

    if retrieval_mode == "never":
        reason = "当前知识库设置为永不检索"
        return {
            "need_retrieval": False,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    if retrieval_mode == "always":
        reason = "当前知识库设置为强制检索"
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    if not settings["enable_query_router"]:
        reason = "Query Router 已关闭，默认执行知识库检索"
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    final_decision: RetrievalDecision = {
        **decision,
        "llm_need_retrieval": decision["need_retrieval"],
        "llm_reason": decision["reason"],
        "override_applied": False,
        "override_reason": "",
        "final_need_retrieval": decision["need_retrieval"],
    }

    if (
        not decision["need_retrieval"]
        and should_force_retrieval_by_profile(query, profile)
    ):
        override_reason = "问题关键词命中当前知识库文件画像，已强制检索"
        return {
            **final_decision,
            "need_retrieval": True,
            "final_need_retrieval": True,
            "rewritten_query": query,
            "override_applied": True,
            "override_reason": override_reason,
            "reason": (
                f"{decision['reason']}；{override_reason}"
            ),
        }

    return final_decision


def build_knowledge_base_profile(inputs: ChainInput) -> str:
    """根据当前知识库文件列表生成轻量知识库画像。

    先不引入新的摘要表，使用文件名、类型和索引状态帮助 Router 判断
    用户问题是否可能需要知识库。后续可以将这里替换为文件摘要/标签表。
    """
    context = get_cached_knowledge_base_context(
        user_id=inputs["user_id"],
        knowledge_base_id=inputs["knowledge_base_id"],
        load_rows=lambda: get_knowledge_base_files(
            knowledge_base_id=inputs["knowledge_base_id"],
            user_id=inputs["user_id"],
        ),
        max_profile_files=MAX_KNOWLEDGE_PROFILE_FILES,
    )
    return context.profile


def format_route_info(inputs: ChainInput) -> str:
    """将检索路由结果格式化为回答阶段的系统提示信息。"""
    decision = normalize_retrieval_decision(
        inputs.get("retrieval_decision"),
    )
    need_retrieval = "是" if decision["need_retrieval"] else "否"
    query = decision["rewritten_query"] or inputs.get(
        "standalone_question",
        "",
    )
    return (
        f"是否需要知识库检索：{need_retrieval}\n"
        f"检索/改写问题：{query}\n"
        f"判断原因：{decision['reason']}"
    )


def get_res_doc(inputs: dict[str, Any]) -> str:
    """将检索到的文档列表格式化为提示词上下文。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    docs = filter_relevant_reference_documents(
        inputs.get("context", []),
        rerank_score_threshold=float(settings["rerank_score_threshold"]),
    )
    context_parts = []

    for index, doc in enumerate(docs, start=1):
        metadata = doc.metadata
        source = metadata.get("file_name") or metadata.get("source", "")
        chunk_index = metadata.get("chunk_index", "")
        context_parts.append(
            f"[片段 {index}]"
            f" 来源：{source}"
            f" chunk：{chunk_index}\n"
            f"{doc.page_content}"
        )

    return "\n\n".join(context_parts)


def serialize_reference_documents(
    docs: list[Document],
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """将检索到的文档片段转换为前端可展示的引用结构。

    返回的每个引用对象将来源信息和排序分数扁平放在顶层，
    方便前端直接读取。file_name 使用数据库中用户上传的原始文件名，
    而非磁盘存储的统称名。
    """
    from app.repositories.knowledge_file_repository import (
        get_file_original_names,
    )

    # 批量查询 file_id → 原始文件名 映射
    file_ids = list({
        doc.metadata.get("file_id")
        for doc in docs
        if isinstance(doc, Document) and doc.metadata.get("file_id")
    })
    original_names = (
        get_file_original_names(user_id, file_ids)
        if user_id is not None and file_ids
        else {}
    )

    references = []
    relevant_docs = filter_relevant_reference_documents(
        docs,
        rerank_score_threshold=get_reference_threshold_from_docs(docs),
    )
    for index, doc in enumerate(relevant_docs, start=1):
        metadata = doc.metadata
        doc_file_id = metadata.get("file_id", "")

        references.append({
            "index": index,
            "content": doc.page_content,
            "source": metadata.get("source"),
            "file_id": doc_file_id,
            "file_name": original_names.get(doc_file_id)
                          or metadata.get("file_name"),
            "file_type": metadata.get("file_type"),
            "chunk_index": metadata.get("chunk_index"),
            "retrieval_sources": metadata.get("retrieval_sources"),
            "vector_score": metadata.get("vector_score"),
            "fulltext_score": metadata.get("fulltext_score"),
            "rrf_score": metadata.get("rrf_score"),
            "rerank_score": metadata.get("rerank_score"),
        })

    return references


def get_knowledge_base_file_ids(
    user_id: int,
    knowledge_base_id: UUID,
) -> list[str]:
    """查询知识库中已完成向量化的文件 ID 列表。

    只返回 status='indexed' 的文件，避免 ChromaDB 查找未向量化
    文件 ID 时触发 HNSW 内部错误。
    """
    context = get_cached_knowledge_base_context(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        load_rows=lambda: get_knowledge_base_files(
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
        ),
        max_profile_files=MAX_KNOWLEDGE_PROFILE_FILES,
    )
    return context.file_ids


def retrieve_documents(inputs: ChainInput) -> RetrievedDocs:
    """根据当前知识库范围执行混合检索。"""
    user_id = inputs["user_id"]
    knowledge_base_id = inputs["knowledge_base_id"]
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    decision = normalize_retrieval_decision(
        inputs.get("retrieval_decision"),
    )
    if not decision["need_retrieval"]:
        return []

    query = decision["rewritten_query"] or inputs["standalone_question"]

    file_ids = get_knowledge_base_file_ids(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
    )
    if not file_ids:
        return []

    docs = get_hybrid_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=int(settings["top_k"]),
        vector_k=int(settings["vector_top_k"]),
        fulltext_k=int(settings["fulltext_top_k"]),
        rrf_k=int(settings["rrf_k"]),
        rerank=bool(settings["enable_rerank"]),
    )
    diagnostics = get_retrieval_diagnostics()
    if diagnostics is not None:
        diagnostics["settings"] = settings
        # LCEL 流式执行过程中 ContextVar 可能跨 Runnable 丢失。
        # 将诊断挂到文档 metadata，确保后续 SSE 和落库能稳定读取。
        for doc in docs:
            doc.metadata["retrieval_diagnostics"] = diagnostics
            doc.metadata["rerank_score_threshold"] = settings[
                "rerank_score_threshold"
            ]
    return docs


def extract_retrieval_diagnostics_from_docs(
    docs: list[Document],
) -> dict[str, Any] | None:
    """从检索文档 metadata 中提取混合检索诊断信息。"""
    for doc in docs:
        diagnostics = doc.metadata.get("retrieval_diagnostics")
        if isinstance(diagnostics, dict):
            return diagnostics
    return None


# 组建问答链
def get_chain(user_id: int) -> RunnableSerializable:
    """
    创建模型、提示词模板和输出解析器，组建 LCEL 问答链。

    第一次调用由 LLM 补充用户问题，再在当前知识库范围内混合检索。
    第二次调用将检索上下文和用户问题交给 LLM 生成答案。
    """
    model_config = get_effective_chat_model_config(user_id)
    model = create_openai_compatible_chat_model(model_config.settings)
    llm_diagnostics = serialize_llm_diagnostics(
        model_config.settings,
        model_config.credential_mode,
    )

    # 第一次调用：由LLM补充用户提问，再进行混合检索
    condense_question_system_template = (
        "请根据聊天记录完善用户最新的问题，"
        "如果用户最新的问题不需要完善则返回用户的问题。"
        "只返回完善后的问题，不要解释。"
    )
    condense_question_prompt = ChatPromptTemplate([
        ("system", condense_question_system_template),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])

    def has_no_chat_history(inputs: ChainInput) -> bool:
        return not bool(inputs.get("chat_history"))

    def get_user_input(inputs: ChainInput) -> str:
        return inputs["input"]

    no_history_question: Runnable[ChainInput, str] = (
        RunnableLambda(get_user_input)
    )
    history_question: RunnableSerializable[ChainInput, str] = (
        condense_question_prompt
        | model
        | StrOutputParser()
    )
    standalone_question: RunnableSerializable[ChainInput, str] = (
        RunnableBranch(
            (RunnableLambda(has_no_chat_history), no_history_question),
            cast(Any, history_question),
        )
    )

    retrieve_docs: RunnableSerializable[ChainInput, RetrievedDocs] = (
        RunnableLambda(retrieve_documents)
    )

    router_system_prompt = (
        "你是 RAG 问题路由器。请判断用户最新问题是否需要检索当前知识库。"
        "你可以参考聊天记录、改写后的问题，以及当前知识库文件画像。"
        "如果问题是问候、闲聊、让你介绍能力、或不依赖知识库的一般对话，"
        "need_retrieval=false。"
        "如果问题提到文档、文件、知识库、法律条文、技术资料，或可能需要"
        "根据当前知识库事实回答，need_retrieval=true。"
        "如果不确定，必须选择 need_retrieval=true。"
        "请只输出 JSON，不要 Markdown，不要解释。JSON 格式："
        '{{"need_retrieval": true, "rewritten_query": "用于检索的中文问题", '
        '"reason": "一句话原因"}}'
        "\n\n当前知识库文件画像：\n{knowledge_profile}"
    )
    router_prompt = ChatPromptTemplate([
        ("system", router_system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "用户原始问题：{input}\n改写后的问题：{standalone_question}"),
    ])
    router_chain: RunnableSerializable[ChainInput, RetrievalDecision] = (
        router_prompt
        | model
        | StrOutputParser()
        | RunnableLambda(parse_retrieval_decision)
    )
    configured_router_decision: RunnableSerializable[
        ChainInput,
        RetrievalDecision,
    ] = RunnableLambda(build_configured_retrieval_decision)
    retrieval_router: RunnableSerializable[ChainInput, RetrievalDecision] = (
        RunnableBranch(
            (RunnableLambda(should_run_query_router), router_chain),
            configured_router_decision,
        )
    )

    # 第二次调用：由检索上下文和用户问题生成答案
    system_prompt = (
        "你是一个问答助手。系统会先判断本轮是否需要检索知识库。"
        "如果“是否需要知识库检索”为“否”，请直接自然回答用户，不要声称"
        "参考了知识库。"
        "如果“是否需要知识库检索”为“是”，请优先使用检索到的上下文片段"
        "回答；如果上下文为空或没有答案，就说不知道。"
        "请使用简洁的话语回答用户。"
        "\n\n"
        "路由信息：\n{route_info}"
        "\n\n"
        "检索上下文：\n"
        "{context}"
    )
    qa_prompt = ChatPromptTemplate([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])
    qa_chain = (
        RunnablePassthrough.assign(
            route_info=RunnableLambda(format_route_info),
            context=RunnableLambda(get_res_doc)
        )
        | qa_prompt
        | model
    )

    return (
        RunnablePassthrough.assign(
            standalone_question=standalone_question
        )
        .assign(llm_diagnostics=RunnableLambda(lambda _: llm_diagnostics))
        .assign(retrieval_settings=RunnableLambda(load_retrieval_settings))
        .assign(knowledge_profile=RunnableLambda(build_knowledge_base_profile))
        .assign(raw_retrieval_decision=retrieval_router)
        .assign(retrieval_decision=RunnableLambda(finalize_retrieval_decision))
        .assign(context=retrieve_docs)
        .assign(answer=qa_chain)
    )


# 从链中获取结果
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
    llm_diagnostics: dict[str, Any] | None = None
    first_answer_token_recorded = False
    for chunk in response:
        for chunk_key, stage in RAG_STAGE_TIMING_FIELDS.items():
            if chunk_key in chunk:
                record_rag_stage(stage)

        if isinstance(chunk.get("llm_diagnostics"), dict):
            llm_diagnostics = chunk["llm_diagnostics"]

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
            cache_diagnostics = get_knowledge_profile_cache_diagnostics()
            if cache_diagnostics is not None:
                diagnostics_with_timing.update(cache_diagnostics)
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
