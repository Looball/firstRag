import json
from collections.abc import Iterator
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
from app.services.user_settings_service import get_effective_chat_model_settings
from app.services.llm_service import create_openai_compatible_chat_model
from app.services.retrieval.hybrid_retriever import get_hybrid_documents


type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]
type RagStreamEvent = dict[str, Any]
type RetrievalDecision = dict[str, Any]


REFERENCE_RERANK_SCORE_THRESHOLD = 0.0
MAX_KNOWLEDGE_PROFILE_FILES = 30


def create_chat_model(user_id: int) -> ChatOpenAI:
    """创建当前用户生效的 OpenAI 兼容聊天模型。"""
    settings = get_effective_chat_model_settings(user_id)
    return create_openai_compatible_chat_model(settings)


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


def normalize_retrieval_decision(
    decision: dict[str, Any] | None,
) -> RetrievalDecision:
    """规范化检索路由结果，异常或缺失时保守选择检索。"""
    if not isinstance(decision, dict):
        return {
            "need_retrieval": True,
            "rewritten_query": "",
            "reason": "路由结果无效，保守执行知识库检索",
        }

    need_retrieval = decision.get("need_retrieval", True)
    if isinstance(need_retrieval, str):
        need_retrieval = need_retrieval.strip().lower()
        need_retrieval = need_retrieval not in {"false", "0", "no", "否"}
    rewritten_query = str(decision.get("rewritten_query") or "").strip()
    reason = str(decision.get("reason") or "").strip()

    return {
        "need_retrieval": bool(need_retrieval),
        "rewritten_query": rewritten_query,
        "reason": reason or "未提供原因",
    }


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


def build_knowledge_base_profile(inputs: ChainInput) -> str:
    """根据当前知识库文件列表生成轻量知识库画像。

    先不引入新的摘要表，使用文件名、类型和索引状态帮助 Router 判断
    用户问题是否可能需要知识库。后续可以将这里替换为文件摘要/标签表。
    """
    rows = get_knowledge_base_files(
        knowledge_base_id=inputs["knowledge_base_id"],
        user_id=inputs["user_id"],
    )
    indexed_rows = [
        row
        for row in rows
        if row.get("status") == "indexed"
    ]
    if not indexed_rows:
        return "当前知识库没有已完成索引的文件。"

    profile_lines = [
        "当前知识库已索引文件：",
    ]
    for index, row in enumerate(
        indexed_rows[:MAX_KNOWLEDGE_PROFILE_FILES],
        start=1,
    ):
        file_name = row.get("original_name") or "未命名文件"
        mime_type = row.get("mime_type") or "未知类型"
        profile_lines.append(f"{index}. {file_name}（{mime_type}）")

    remaining_count = len(indexed_rows) - MAX_KNOWLEDGE_PROFILE_FILES
    if remaining_count > 0:
        profile_lines.append(f"...另有 {remaining_count} 个已索引文件。")

    return "\n".join(profile_lines)


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
    docs = filter_relevant_reference_documents(inputs.get("context", []))
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
    relevant_docs = filter_relevant_reference_documents(docs)
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
    rows = get_knowledge_base_files(
        knowledge_base_id=knowledge_base_id,
        user_id=user_id,
    )
    return [
        str(row["id"])
        for row in rows
        if row.get("status") == "indexed"
    ]


def retrieve_documents(inputs: ChainInput) -> RetrievedDocs:
    """根据当前知识库范围执行混合检索。"""
    user_id = inputs["user_id"]
    knowledge_base_id = inputs["knowledge_base_id"]
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

    return get_hybrid_documents(
        query=query,
        user_id=user_id,
        file_ids=file_ids,
        k=5,
        vector_k=20,
        fulltext_k=20,
        rrf_k=20,
        rerank=True,
    )


# 组建问答链
def get_chain(user_id: int) -> RunnableSerializable:
    """
    创建模型、提示词模板和输出解析器，组建 LCEL 问答链。

    第一次调用由 LLM 补充用户问题，再在当前知识库范围内混合检索。
    第二次调用将检索上下文和用户问题交给 LLM 生成答案。
    """
    model = create_chat_model(user_id)

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
        | StrOutputParser()
    )

    return (
        RunnablePassthrough.assign(
            standalone_question=standalone_question
        )
        .assign(knowledge_profile=RunnableLambda(build_knowledge_base_profile))
        .assign(retrieval_decision=router_chain)
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
    response = chain.stream({
        "input": user_input,
        "chat_history": chat_history,
        "user_id": user_id,
        "knowledge_base_id": knowledge_base_id,
    })

    sources_sent = False
    for chunk in response:
        if "context" in chunk and not sources_sent:
            sources = serialize_reference_documents(
                chunk["context"],
                user_id=user_id,
            )
            # 没有可信引用时不发送 sources 事件，避免前端展示空 Sources。
            if sources:
                yield {
                    "type": "sources",
                    "sources": sources,
                }
            sources_sent = True

        if "answer" in chunk:
            yield {
                "type": "answer",
                "content": chunk["answer"],
            }
