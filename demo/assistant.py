"""兼容入口：RAG服务实现位于app.services。"""

from app.services.rag_service import (
    get_answer,
    get_chain,
    get_res_doc,
    get_retriever,
)
from app.services.streamlit_service import render_stream, run_streamlit_app

__all__ = [
    "get_answer",
    "get_chain",
    "get_res_doc",
    "get_retriever",
    "render_stream",
]


def main() -> None:
    run_streamlit_app()


if __name__ == "__main__":
    main()
