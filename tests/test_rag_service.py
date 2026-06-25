"""RAG 引用过滤逻辑的回归测试。"""

import unittest
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.services.rag_service import (
    build_knowledge_base_profile,
    get_res_doc,
    get_chain,
    normalize_retrieval_decision,
    parse_retrieval_decision,
    retrieve_documents,
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


class RagQueryRouterTests(unittest.TestCase):
    """验证 Query Router 的解析、画像和检索开关行为。"""

    def test_parse_retrieval_decision_accepts_json_block(self) -> None:
        """Router 输出 JSON 代码块时也应能解析为结构化结果。"""
        decision = parse_retrieval_decision(
            '```json\n'
            '{"need_retrieval": false, '
            '"rewritten_query": "你好", '
            '"reason": "普通问候"}\n'
            '```'
        )

        self.assertFalse(decision["need_retrieval"])
        self.assertEqual(decision["rewritten_query"], "你好")
        self.assertEqual(decision["reason"], "普通问候")

    def test_invalid_router_output_falls_back_to_retrieval(self) -> None:
        """Router 输出不可解析时，应保守执行检索。"""
        decision = parse_retrieval_decision("我觉得不用检索")

        self.assertTrue(decision["need_retrieval"])

    def test_normalize_retrieval_decision_keeps_rewritten_query(self) -> None:
        """路由结果应保留用于检索的问题改写。"""
        decision = normalize_retrieval_decision({
            "need_retrieval": True,
            "rewritten_query": "民事诉讼法 起诉条件",
            "reason": "问题涉及法律文档",
        })

        self.assertTrue(decision["need_retrieval"])
        self.assertEqual(
            decision["rewritten_query"],
            "民事诉讼法 起诉条件",
        )

    def test_retrieve_documents_skips_when_router_says_no(self) -> None:
        """Router 判断无需知识库时，不应执行后续混合检索。"""
        docs = retrieve_documents({
            "user_id": 1,
            "knowledge_base_id": uuid4(),
            "standalone_question": "你好",
            "retrieval_decision": {
                "need_retrieval": False,
                "rewritten_query": "你好",
                "reason": "普通问候",
            },
        })

        self.assertEqual(docs, [])

    def test_build_knowledge_base_profile_uses_indexed_files(self) -> None:
        """知识库画像应只使用已索引文件，供 Router 识别知识库范围。"""
        with unittest.mock.patch(
            "app.services.rag_service.get_knowledge_base_files",
            return_value=[
                {
                    "original_name": "民事诉讼法.pdf",
                    "mime_type": "application/pdf",
                    "status": "indexed",
                },
                {
                    "original_name": "未处理.txt",
                    "mime_type": "text/plain",
                    "status": "pending",
                },
            ],
        ):
            profile = build_knowledge_base_profile({
                "user_id": 1,
                "knowledge_base_id": uuid4(),
            })

        self.assertIn("民事诉讼法.pdf", profile)
        self.assertNotIn("未处理.txt", profile)

    def test_get_chain_stream_renders_router_prompt_json_example(self) -> None:
        """真实链路应能渲染 Router Prompt 中的 JSON 示例。"""
        model = FakeListChatModel(responses=[
            (
                '{"need_retrieval": false, '
                '"rewritten_query": "你好", '
                '"reason": "普通问候"}'
            ),
            "你好！有什么可以帮你的吗？",
        ])

        with unittest.mock.patch(
            "app.services.rag_service.create_chat_model",
            return_value=model,
        ), unittest.mock.patch(
            "app.services.rag_service.get_knowledge_base_files",
            return_value=[],
        ):
            chain = get_chain(user_id=1)
            chunks = list(chain.stream({
                "input": "你好",
                "chat_history": [],
                "user_id": 1,
                "knowledge_base_id": uuid4(),
            }))

        self.assertTrue(any("answer" in chunk for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
