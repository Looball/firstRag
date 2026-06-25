"""聊天服务流式保存行为的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.chat_service import stream_answer_and_save


class ChatServiceSourcePersistenceTests(unittest.TestCase):
    """验证流式回答完成时会持久化引用来源。"""

    def test_stream_answer_and_save_persists_sources_on_completion(
        self,
    ) -> None:
        """sources 事件中的引用应随助手消息最终内容一起保存。"""
        sources = [
            {
                "index": 1,
                "file_name": "民事诉讼法.pdf",
                "content": "相关片段",
            }
        ]

        with patch(
            "app.services.chat_service.stream_rag_response",
            return_value=[
                {"type": "sources", "sources": sources},
                {"type": "answer", "content": "回答"},
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

        self.assertTrue(any("event: sources" in event for event in events))
        self.assertTrue(any("event: done" in event for event in events))
        finish_message.assert_called_once()
        self.assertEqual(finish_message.call_args.kwargs["sources"], sources)


if __name__ == "__main__":
    unittest.main()
