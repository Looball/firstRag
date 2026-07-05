from typing import Any, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnablePassthrough,
    RunnableSerializable,
)

from app.services.llm_service import create_openai_compatible_chat_model
from app.services.chat_attachment_service import build_vision_image_content
from app.services.rag.diagnostics import serialize_llm_diagnostics
from app.services.rag.reference_serializer import get_res_doc
from app.services.rag.retrieval_decision import (
    build_configured_retrieval_decision,
    finalize_retrieval_decision,
    format_route_info,
    parse_retrieval_decision,
    should_run_query_router,
)
from app.services.rag.retrieval_pipeline import (
    build_knowledge_base_profile,
    load_retrieval_settings,
    retrieve_documents,
)
from app.services.rag.types import ChainInput, RetrievalDecision, RetrievedDocs
from app.services.user_settings_service import get_effective_chat_model_config

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
    def build_qa_messages(inputs: ChainInput) -> list:
        """构造最终回答用消息，支持本轮图片附件。"""
        messages = [
            SystemMessage(
                content=system_prompt.format(
                    route_info=format_route_info(inputs),
                    context=get_res_doc(inputs),
                )
            )
        ]
        for role, content in inputs.get("chat_history") or []:
            if role == "human":
                messages.append(HumanMessage(content=content))
            elif role == "ai":
                messages.append(AIMessage(content=content))

        image_attachments = inputs.get("image_attachments") or []
        if image_attachments:
            messages.append(
                HumanMessage(
                    content=[
                        {"type": "text", "text": inputs["input"]},
                        *build_vision_image_content(image_attachments),
                    ]
                )
            )
        else:
            messages.append(HumanMessage(content=inputs["input"]))
        return messages

    qa_chain = (
        RunnableLambda(build_qa_messages)
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
