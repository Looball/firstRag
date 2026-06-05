# 使用os获取环境变量  os.environ.get('')
import os


# 导入类型变量
from typing import Any,TypedDict,cast
from collections.abc import Iterable

from langchain_core.runnables import RunnableSerializable
from langchain_core.vectorstores.base import VectorStoreRetriever
from langchain_core.documents import Document
from langchain_core.runnables import Runnable,RunnableLambda,RunnableBranch,RunnablePassthrough

from streamlit.delta_generator import DeltaGenerator

# 类型别名
type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]

# 导入pydantic
from pydantic import SecretStr


# 导入自定义的 embedding模型
from loadDoc import ZhipuAIEmbeddings

# 使用DeepSeek官方封装的langchain包
from langchain_deepseek import ChatDeepSeek

# 从langchain导入 提示词模版对象
from langchain_core.prompts import ChatPromptTemplate

# 导入langchain 输出解析器
from langchain_core.output_parsers import StrOutputParser

# 导入streamlit包
import streamlit as st

# 创建 向量知识库 检索器
def get_retriever() -> VectorStoreRetriever:

    """ don't need input

    从loadDoc封装好的ZhipuAIembedding创建 embedding对象

    使用环境变量：'ZAI_EMD_API'

    :return: an object of "vectordb.as_retriever"
    """

    # 创建文本嵌入对象
    embedding = ZhipuAIEmbeddings()

    # 导入向量数据库包
    from langchain_chroma import Chroma

    # 指定向量数据库目录
    persist_directory = './vector_db/chroma'
    # 加载数据库
    vectordb = Chroma(
        persist_directory=persist_directory,  # 允许我们将persist_directory目录保存到磁盘上
        embedding_function=embedding
    )

    return vectordb.as_retriever(search_type='similarity',search_kwargs={"k": 2})

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
    """ 创建模型、提示词模版、输出解析器 组建LCEL

    第一次：用户输入 | 提示词 |LLM模型 | OutStr -> 补充用户问题

    第二次：由" 补充用户问题"检索到的上下文 + 补充用户问题 | 提示词模版 | LLM | OutStr -> ans


    :return: ans: str
    """
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("缺少环境变量 DEEPSEEK_API_KEY")

    # 创建 LLM 模型
    model = ChatDeepSeek(
        model="deepseek-v4-flash",
        temperature=0.2,
        max_tokens=8000,
        timeout=None,
        max_retries=2,
        api_key=SecretStr(deepseek_api_key),
    )

    # 创建向量检索器
    retriever = get_retriever()

    # """
    # ——————————————————————————————————————第一次调用—————————————————————————————————————————
    #                     由LLM补充用户提问，再向量检索出本地数据库内容
    # """
    # 让LLM补充用户问题的 系统prompt
    condense_question_system_template = (
        "请根据聊天记录完善用户最新的问题，"
        "如果用户最新的问题不需要完善则返回用户的问题。"
    )


    # 构造提示词模版
    condense_question_prompt = ChatPromptTemplate([
        ("system", condense_question_system_template),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])

    # 检查历史记录
    def has_no_chat_history(x: ChainInput) -> bool:
        return not bool(x.get("chat_history"))

    # 配合has_no_chat_history使用，获取用户第一次的输入
    def get_user_input(x: ChainInput) -> str:
        return x["input"]

    # 没有历史记录时的检索方案
    no_history_retriever: Runnable[ChainInput, RetrievedDocs] = (
            RunnableLambda(get_user_input) | retriever
    )

    # 有历史记录时的检索方案
    history_retriever: RunnableSerializable[ChainInput, RetrievedDocs] = (
            condense_question_prompt
            | model
            | StrOutputParser()
            | retriever
    )

    # 进行向量检索
    retrieve_docs: RunnableSerializable[ChainInput, RetrievedDocs] = RunnableBranch(
        (RunnableLambda(has_no_chat_history), no_history_retriever),
        cast(Any, history_retriever), # 告诉IDE不再做严格检查
    )

    # """
    # ——————————————————————————————————————第二次调用—————————————————————————————————————————
    #                       由检索到的上下文内容 + 用户问题 -> LLM 获取问答结果
    # """
    # 系统提示词
    system_prompt = (
        "你是一个问答任务的助手。 "
        "请使用检索到的上下文片段回答这个问题。 "
        "如果你不知道答案就说不知道。 "
        "请使用简洁的话语回答用户。"
        "\n\n"
        "{context}"
    )

    # 创建提示词模版
    qa_prompt = ChatPromptTemplate(
        [
            ("system", system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ]
    )

    qa_chain = (
            RunnablePassthrough.assign(
                context=RunnableLambda(get_res_doc)
            )  # 使用 get_res_doc 函数整合 qa_prompt 中的 context
            | qa_prompt  # 问答模板
            | model
            | StrOutputParser()  # 规定输出的格式为 str
    )

    # 传入向量数据库的查询结果，并指定将qa_chain的返回结果定义为answer，返回最终链
    qa_history_chain = RunnablePassthrough.assign(
        context=retrieve_docs
    ).assign(answer=qa_chain)  # 将最终结果存为 answer

    return qa_history_chain


# 从链中获取结果
def get_answer(chain:RunnableSerializable, user_input:str, chat_history:list):
    res = chain.stream({
        "input": user_input,
        "chat_history": chat_history
    })

    for r in res:
        if "answer" in r.keys():
            yield r["answer"]


def render_stream(stream:Iterable) -> str :

    output = ""
    placeholder: DeltaGenerator | None = None


    for chunk in stream:
        if chunk is None:
            continue

        output += str(chunk)

        if placeholder is None:
            placeholder = st.empty()
        else:
            placeholder.markdown(output)

    return output


# 展示页面  streamlit
def main():
    """ streamlit 启动程序

    :return:
    """

    st.markdown('### 🦜🔗 RAG本地知识库Demo')

    # st.session_state可以存储用户与应用交互期间的状态与数据
    # 首次使用session，创建messages，存储对话历史
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 首次使用session，创建qa_history_chain，存储检索问答链
    if "qa_history_chain" not in st.session_state:
        st.session_state.qa_history_chain = get_chain()

    # 建立容器 高度为500 px
    messages = st.container(height=550)

    # 遍历展示整个对话历史
    for message in st.session_state.messages:  # 遍历对话历史
        with messages.chat_message(message[0]):  # messages指在容器下显示，chat_message显示用户及ai头像
            st.markdown(message[1])  # 打印内容

    prompt = st.chat_input("Say something")
    if isinstance(prompt, str):

        # 先copy一份过去的历史记录，用于传入chat_history
        history_for_chain = st.session_state.messages.copy()

        # 将用户输入添加到对话列表中  下一次调用
        st.session_state.messages.append(("human", prompt))

        # 显示当前用户输入
        with messages.chat_message("human"):
            st.markdown(prompt)

        # 生成回复
        answer = get_answer(
            chain=st.session_state.qa_history_chain,
            user_input=prompt,
            chat_history=history_for_chain,
        )

        # 流式输出
        with messages.chat_message("ai"):
            output = render_stream(answer)

        # 将输出存入st.session_state.messages
        st.session_state.messages.append(("ai", output))


if __name__ == '__main__':
    main()

