"""聊天服务流式保存行为的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.chat_service import stream_answer_and_save


class ChatServiceSourcePersistenceTests(unittest.TestCase):
    """验证流式回答完成时会持久化引用来源。"""

    def test_stream_answer_and_save_persists_sources_and_retrieval(
        self,
    ) -> None:
        """sources 和 retrieval 应随助手消息最终内容一起保存。"""
        sources = [
            {
                "index": 1,
                "file_name": "民事诉讼法.pdf",
                "content": "相关片段",
            }
        ]
        retrieval = {
            "need_retrieval": True,
            "rewritten_query": "诉讼法",
            "reason": "问题涉及知识库",
            "retrieved_count": 5,
            "source_count": 1,
        }

        with patch(
            "app.services.chat_service.stream_rag_response",
            return_value=[
                {"type": "retrieval", **retrieval},
                {"type": "sources", "sources": sources},
                {"type": "answer", "content": "回答"},
            ],
        ), patch(
            "app.services.chat_service.finish_assistant_message",
        ) as finish_message:
            assistant_message_id = uuid4()
            events = list(stream_answer_and_save(
                chain=object(),
                user_input="什么是诉讼法",
                history=[],
                conversation_id=uuid4(),
                assistant_message_id=assistant_message_id,
                user_id=1,
                knowledge_base_id=uuid4(),
            ))

        self.assertTrue(any("event: sources" in event for event in events))
        self.assertTrue(any("event: done" in event for event in events))
        self.assertTrue(
            any(
                f'"message_id": "{assistant_message_id}"' in event
                for event in events
            ),
        )
        finish_message.assert_called_once()
        self.assertEqual(finish_message.call_args.kwargs["sources"], sources)
        saved_retrieval = finish_message.call_args.kwargs["retrieval"]
        self.assertTrue(saved_retrieval["need_retrieval"])
        self.assertEqual(saved_retrieval["rewritten_query"], "诉讼法")
        timing = saved_retrieval["diagnostics"]["timing"]
        self.assertIn("first_answer_token_ms", timing)
        self.assertIn("answer_stream_ms", timing)
        self.assertIn("chat_stream_total_ms", timing)
        self.assertGreaterEqual(timing["chat_stream_total_ms"], 0.0)

    def test_stream_answer_and_save_merges_llm_usage_before_persisting(
        self,
    ) -> None:
        """后到达的 LLM usage 应合并进最终持久化的 retrieval。"""
        retrieval = {
            "need_retrieval": True,
            "rewritten_query": "诉讼法",
            "reason": "问题涉及知识库",
            "retrieved_count": 0,
            "source_count": 0,
            "diagnostics": {
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }
            },
        }
        llm_usage = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
        }

        with patch(
            "app.services.chat_service.stream_rag_response",
            return_value=[
                {"type": "retrieval", **retrieval},
                {"type": "answer", "content": "回答"},
                {"type": "llm_usage", "llm": llm_usage},
            ],
        ), patch(
            "app.services.chat_service.finish_assistant_message",
        ) as finish_message:
            events = list(stream_answer_and_save(
                chain=object(),
                user_input="什么是诉讼法",
                history=[],
                conversation_id=uuid4(),
                assistant_message_id=uuid4(),
                user_id=1,
                knowledge_base_id=uuid4(),
            ))

        self.assertTrue(any("event: llm_usage" in event for event in events))
        saved_retrieval = finish_message.call_args.kwargs["retrieval"]
        saved_llm = saved_retrieval["diagnostics"]["llm"]
        self.assertEqual(saved_llm["prompt_tokens"], 12)
        self.assertEqual(saved_llm["completion_tokens"], 3)
        self.assertEqual(saved_llm["total_tokens"], 15)


if __name__ == "__main__":
    unittest.main()
