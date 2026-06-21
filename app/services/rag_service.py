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
from app.services.llm_service import create_system_chat_model
from app.services.retrieval.hybrid_retriever import get_hybrid_documents


type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]
type RagStreamEvent = dict[str, Any]


def create_chat_model() -> ChatOpenAI:
    """创建系统配置的 OpenAI 兼容聊天模型。"""
    return create_system_chat_model()


def get_res_doc(inputs: dict[str, Any]) -> str:
    """将检索到的文档列表格式化为提示词上下文。"""
    docs = inputs.get("context", [])
    context_parts = []

    for index, doc in enumerate(docs, start=1):
        if not isinstance(doc, Document):
            continue

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
    for index, doc in enumerate(docs, start=1):
        if not isinstance(doc, Document):
            continue

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
    query = inputs["standalone_question"]

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
def get_chain() -> RunnableSerializable:
    """
    创建模型、提示词模板和输出解析器，组建 LCEL 问答链。

    第一次调用由 LLM 补充用户问题，再在当前知识库范围内混合检索。
    第二次调用将检索上下文和用户问题交给 LLM 生成答案。
    """
    model = create_chat_model()

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

    # 第二次调用：由检索上下文和用户问题生成答案
    system_prompt = (
        "你是一个问答任务的助手。 "
        "请使用检索到的上下文片段回答这个问题。 "
        "如果上下文中没有答案，就说不知道。 "
        "请使用简洁的话语回答用户。"
        "\n\n"
        "{context}"
    )
    qa_prompt = ChatPromptTemplate([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])
    qa_chain = (
        RunnablePassthrough.assign(
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
            yield {
                "type": "sources",
                "sources": serialize_reference_documents(
                    chunk["context"],
                    user_id=user_id,
                ),
            }
            sources_sent = True

        if "answer" in chunk:
            yield {
                "type": "answer",
                "content": chunk["answer"],
            }
