from collections.abc import Iterable
from uuid import UUID

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.services.rag_service import get_answer, get_chain


def render_stream(stream: Iterable) -> str:
    """将回答流逐步渲染到Streamlit页面。"""
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


# 展示页面 Streamlit
def run_streamlit_app() -> None:
    """Streamlit启动程序。"""
    st.markdown("### 🦜🔗 RAG本地知识库Demo")
    user_id = st.sidebar.number_input(
        "用户 ID",
        min_value=1,
        value=1,
        step=1,
    )
    knowledge_base_id_text = st.sidebar.text_input("知识库 ID")

    # 首次使用session时创建messages，存储对话历史
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 首次使用session时创建qa_history_chain，存储检索问答链
    if "qa_history_chain" not in st.session_state:
        st.session_state.qa_history_chain = get_chain()

    messages = st.container(height=550)

    # 遍历展示整个对话历史
    for message in st.session_state.messages:
        with messages.chat_message(message[0]):
            st.markdown(message[1])

    prompt = st.chat_input("Say something")
    if isinstance(prompt, str):
        if not knowledge_base_id_text:
            st.error("请先在侧边栏填写知识库 ID")
            return

        try:
            knowledge_base_id = UUID(knowledge_base_id_text)
        except ValueError:
            st.error("知识库 ID 必须是合法 UUID")
            return

        # 复制历史记录，用于传入chat_history
        history_for_chain = st.session_state.messages.copy()

        # 将用户输入添加到对话列表
        st.session_state.messages.append(("human", prompt))

        with messages.chat_message("human"):
            st.markdown(prompt)

        answer = get_answer(
            chain=st.session_state.qa_history_chain,
            user_input=prompt,
            chat_history=history_for_chain,
            user_id=int(user_id),
            knowledge_base_id=knowledge_base_id,
        )

        # 流式输出
        with messages.chat_message("ai"):
            output = render_stream(answer)

        st.session_state.messages.append(("ai", output))
