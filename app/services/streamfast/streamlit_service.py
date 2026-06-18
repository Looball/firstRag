"""Streamlit 兼容演示服务。"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.services.rag_service import get_chain, stream_rag_response


def render_sources(sources: list[dict[str, Any]]) -> None:
    """在 Streamlit 中渲染检索到的引用片段。"""
    if not sources:
        return

    with st.expander("参考片段", expanded=False):
        for source in sources:
            file_name = source.get("file_name") or source.get("source") or "未知来源"
            chunk_index = source.get("chunk_index")
            title = f"{file_name}"
            if chunk_index is not None:
                title += f" · chunk {chunk_index}"

            st.markdown(f"**{title}**")
            st.caption(
                " | ".join(
                    str(item)
                    for item in [
                        f"RRF: {source['rrf_score']:.4f}"
                        if isinstance(source.get("rrf_score"), int | float)
                        else None,
                        f"Rerank: {source['rerank_score']:.4f}"
                        if isinstance(source.get("rerank_score"), int | float)
                        else None,
                    ]
                    if item
                )
            )
            st.markdown(source.get("content") or "")


def render_stream(stream: Iterable[Any]) -> str:
    """将回答流逐步渲染到 Streamlit 页面。

    兼容两种输入：
    1. 旧版 `Iterator[str]`
    2. 新版 `stream_rag_response` 返回的事件流
    """
    output = ""
    placeholder: DeltaGenerator | None = None

    for chunk in stream:
        if chunk is None:
            continue

        if isinstance(chunk, dict):
            event_type = chunk.get("type")
            if event_type == "sources":
                # 新版 RAG 会先产出引用来源，再产出答案分片。
                render_sources(chunk.get("sources") or [])
                continue
            if event_type != "answer":
                continue
            content = str(chunk.get("content") or "")
        else:
            content = str(chunk)

        output += content
        if placeholder is None:
            placeholder = st.empty()
        placeholder.markdown(output)

    return output


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

        answer_stream = stream_rag_response(
            chain=st.session_state.qa_history_chain,
            user_input=prompt,
            chat_history=history_for_chain,
            user_id=int(user_id),
            knowledge_base_id=knowledge_base_id,
        )

        with messages.chat_message("ai"):
            output = render_stream(answer_stream)

        st.session_state.messages.append(("ai", output))
