import os
from typing import Any, cast

from langchain_chroma import Chroma
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
from langchain_core.vectorstores.base import VectorStoreRetriever
from langchain_deepseek import ChatDeepSeek
from pydantic import SecretStr

from app.services.embedding_service import ZhipuAIEmbeddings


type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]


# 创建向量知识库检索器
def get_retriever() -> VectorStoreRetriever:
    """
    从本地Chroma向量数据库创建检索器。

    使用环境变量：ZAI_EMD_API
    """
    embedding = ZhipuAIEmbeddings()
    vectordb = Chroma(
        persist_directory="./vector_db/chroma",
        embedding_function=embedding,
    )
    return vectordb.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 2},
    )


# 提取检索器文本
def get_res_doc(inputs: dict[str, Any]) -> str:
    docs = inputs.get("context", [])
    return "\n\n".join(
        doc.page_content
        for doc in docs
        if isinstance(doc, Document)
    )


# 组建问答链
def get_chain() -> RunnableSerializable:
    """
    创建模型、提示词模板和输出解析器，组建LCEL问答链。

    第一次调用由LLM补充用户问题，再检索本地向量数据库。
    第二次调用将检索上下文和用户问题交给LLM生成答案。
    """
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("缺少环境变量 DEEPSEEK_API_KEY")

    # 创建LLM模型
    model = ChatDeepSeek(
        model="deepseek-v4-flash",
        temperature=0.2,
        max_tokens=8000,
        timeout=None,
        max_retries=2,
        streaming=True,
        api_key=SecretStr(deepseek_api_key),
    )

    # 创建向量检索器
    retriever = get_retriever()

    # 第一次调用：由LLM补充用户提问，再进行向量检索
    condense_question_system_template = (
        "请根据聊天记录完善用户最新的问题，"
        "如果用户最新的问题不需要完善则返回用户的问题。"
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

    # 没有历史记录时直接使用用户输入检索
    no_history_retriever: Runnable[ChainInput, RetrievedDocs] = (
        RunnableLambda(get_user_input) | retriever
    )

    # 有历史记录时先补充用户问题，再进行检索
    history_retriever: RunnableSerializable[ChainInput, RetrievedDocs] = (
        condense_question_prompt
        | model
        | StrOutputParser()
        | retriever
    )

    retrieve_docs: RunnableSerializable[ChainInput, RetrievedDocs] = (
        RunnableBranch(
            (RunnableLambda(has_no_chat_history), no_history_retriever),
            cast(Any, history_retriever),
        )
    )

    # 第二次调用：由检索上下文和用户问题生成答案
    system_prompt = (
        "你是一个问答任务的助手。 "
        "请使用检索到的上下文片段回答这个问题。 "
        "如果你不知道答案就说不知道。 "
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

    return RunnablePassthrough.assign(
        context=retrieve_docs
    ).assign(answer=qa_chain)


# 从链中获取结果
def get_answer(
    chain: RunnableSerializable,
    user_input: str,
    chat_history: list,
):
    response = chain.stream({
        "input": user_input,
        "chat_history": chat_history,
    })

    for chunk in response:
        if "answer" in chunk:
            yield chunk["answer"]
