"""RAG 引用过滤逻辑的回归测试。"""

import unittest
from uuid import uuid4

from langchain_core.documents import Document

from app.services.rag_service import (
    get_res_doc,
    serialize_reference_documents,
    stream_rag_response,
)


class FakeStreamingChain:
    """用于模拟 LCEL 链 stream 输出的轻量测试替身。"""

    def __init__(self, chunks: list[dict]) -> None:
        """保存待输出的 stream chunk。"""
        self.chunks = chunks

    def stream(self, inputs: dict) -> list[dict]:
        """返回预置 chunk，模拟 LangChain 的流式迭代结果。"""
        return self.chunks


class RagReferenceFilteringTests(unittest.TestCase):
    """验证低相关检索片段不会进入上下文和前端来源。"""

    def test_serialize_reference_documents_filters_negative_rerank_score(
        self,
    ) -> None:
        """负相关性分数的文档不应展示为 Sources。"""
        docs = [
            Document(
                page_content="弱相关内容",
                metadata={
                    "file_id": str(uuid4()),
                    "file_name": "irrelevant.pdf",
                    "rerank_score": -2.56,
                },
            ),
            Document(
                page_content="强相关内容",
                metadata={
                    "file_id": str(uuid4()),
                    "file_name": "relevant.pdf",
                    "rerank_score": 1.25,
                },
            ),
        ]

        references = serialize_reference_documents(docs)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["content"], "强相关内容")
        self.assertEqual(references[0]["file_name"], "relevant.pdf")

    def test_get_res_doc_excludes_low_relevance_context(self) -> None:
        """低相关片段不应进入最终提示词上下文。"""
        context = get_res_doc({
            "context": [
                Document(
                    page_content="不该进入上下文",
                    metadata={
                        "file_name": "bad.pdf",
                        "chunk_index": 1,
                        "rerank_score": -0.1,
                    },
                ),
                Document(
                    page_content="应该进入上下文",
                    metadata={
                        "file_name": "good.pdf",
                        "chunk_index": 2,
                        "rerank_score": 0.2,
                    },
                ),
            ]
        })

        self.assertNotIn("不该进入上下文", context)
        self.assertIn("应该进入上下文", context)

    def test_stream_rag_response_skips_empty_sources_event(self) -> None:
        """全部引用被过滤时，不发送 sources 事件。"""
        chain = FakeStreamingChain([
            {
                "context": [
                    Document(
                        page_content="弱相关内容",
                        metadata={"rerank_score": -1.0},
                    )
                ]
            },
            {"answer": "你好！"},
        ])

        events = list(stream_rag_response(
            chain=chain,
            user_input="你好",
            chat_history=[],
            user_id=1,
            knowledge_base_id=uuid4(),
        ))

        self.assertEqual(
            [event["type"] for event in events],
            ["answer"],
        )
        self.assertEqual(events[0]["content"], "你好！")


if __name__ == "__main__":
    unittest.main()
