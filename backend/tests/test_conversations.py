"""会话路由的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import get_current_user_id
from app.main import app


class CreateConversationTests(unittest.TestCase):
    """验证创建会话的知识库权限校验。"""

    def setUp(self) -> None:
        """为每个测试注入固定的认证用户。"""
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.client = TestClient(app)
        self.knowledge_base_id = uuid4()

    def tearDown(self) -> None:
        """清理路由依赖覆盖，避免污染其他测试。"""
        app.dependency_overrides.pop(get_current_user_id, None)
        self.client.close()

    def test_create_conversation_returns_404_for_inaccessible_knowledge_base(
        self,
    ) -> None:
        """不存在或无权访问的知识库不应被误报为服务器错误。"""
        with patch(
            "app.api.conversations.knowledge_base_exists",
            return_value=False,
        ), patch(
            "app.api.conversations.create_conversation_record",
        ) as create_record:
            response = self.client.post(
                f"/chat/knowledge-bases/{self.knowledge_base_id}/conversations",
                json={"title": "测试会话"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "知识库不存在"})
        create_record.assert_not_called()

    def test_create_conversation_persists_for_accessible_knowledge_base(self) -> None:
        """可访问的知识库仍使用原有仓库调用创建会话。"""
        conversation_id = uuid4()
        conversation = {
            "id": conversation_id,
            "knowledge_base_id": self.knowledge_base_id,
            "title": "测试会话",
        }
        with patch(
            "app.api.conversations.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.conversations.create_conversation_record",
            return_value=conversation,
        ) as create_record:
            response = self.client.post(
                f"/chat/knowledge-bases/{self.knowledge_base_id}/conversations",
                json={"title": "测试会话"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        create_record.assert_called_once_with(
            1,
            self.knowledge_base_id,
            "测试会话",
        )

    def test_get_messages_returns_persisted_sources_and_retrieval(self) -> None:
        """历史消息接口应返回已持久化的引用来源和检索状态。"""
        conversation_id = uuid4()
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
            "app.api.conversations.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.conversations.get_user_conversation_messages",
            return_value=[
                {
                    "id": uuid4(),
                    "role": "assistant",
                    "content": "回答",
                    "status": "completed",
                    "error_message": None,
                    "sources": sources,
                    "retrieval": retrieval,
                    "feedback_id": 7,
                    "feedback_rating": "negative",
                    "feedback_reason": "missing_answer",
                    "feedback_note": "没有回答核心问题",
                    "feedback_metadata": {"status": "completed"},
                    "feedback_created_at": "2026-06-25T00:00:02+08:00",
                    "feedback_updated_at": "2026-06-25T00:00:02+08:00",
                    "source_feedbacks": [
                        {
                            "id": "11",
                            "source_index": 1,
                            "knowledge_file_id": None,
                            "chunk_index": 2,
                            "rating": "useful",
                            "note": None,
                            "metadata": {},
                            "created_at": "2026-06-25T00:00:03+08:00",
                            "updated_at": "2026-06-25T00:00:03+08:00",
                        }
                    ],
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ):
            response = self.client.get(
                f"/chat/conversations/{conversation_id}/messages",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["messages"][0]["sources"][0]["feedback"]["rating"],
            "useful",
        )
        self.assertEqual(
            response.json()["messages"][0]["retrieval"],
            retrieval,
        )
        self.assertEqual(
            response.json()["messages"][0]["feedback"],
            {
                "id": "7",
                "rating": "negative",
                "reason": "missing_answer",
                "note": "没有回答核心问题",
                "metadata": {"status": "completed"},
                "created_at": "2026-06-25T00:00:02+08:00",
                "updated_at": "2026-06-25T00:00:02+08:00",
            },
        )

    def test_get_messages_returns_404_for_inaccessible_conversation(self) -> None:
        """跨用户或已软删除的会话不应继续读取消息。"""
        conversation_id = uuid4()
        with patch(
            "app.api.conversations.conversation_exists",
            return_value=False,
        ), patch(
            "app.api.conversations.get_user_conversation_messages",
        ) as get_messages:
            response = self.client.get(
                f"/chat/conversations/{conversation_id}/messages",
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "会话不存在"})
        get_messages.assert_not_called()

    def test_submit_message_feedback_upserts_for_owned_assistant_message(
        self,
    ) -> None:
        """用户可以对自己的助手消息提交或更新质量反馈。"""
        with patch(
            "app.api.conversations.get_user_assistant_message",
            return_value={
                "id": 42,
                "role": "assistant",
                "status": "completed",
                "conversation_id": uuid4(),
            },
        ) as get_message, patch(
            "app.api.conversations.upsert_message_feedback",
            return_value={
                "id": 9,
                "user_id": 1,
                "message_id": 42,
                "rating": "negative",
                "reason": "missing_answer",
                "note": "没有回答核心问题",
                "metadata": {"status": "completed"},
                "created_at": "2026-06-25T00:00:02+08:00",
                "updated_at": "2026-06-25T00:00:03+08:00",
            },
        ) as upsert_feedback:
            response = self.client.post(
                "/chat/messages/42/feedback",
                json={
                    "rating": "negative",
                    "reason": "missing_answer",
                    "note": " 没有回答核心问题 ",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["feedback"]["rating"], "negative")
        self.assertEqual(response.json()["feedback"]["note"], "没有回答核心问题")
        get_message.assert_called_once_with(1, 42)
        upsert_feedback.assert_called_once_with(
            user_id=1,
            message_id=42,
            rating="negative",
            reason="missing_answer",
            note="没有回答核心问题",
            metadata={"status": "completed"},
        )

    def test_submit_message_feedback_returns_404_for_inaccessible_message(
        self,
    ) -> None:
        """跨用户或非助手消息不能提交反馈。"""
        with patch(
            "app.api.conversations.get_user_assistant_message",
            return_value=None,
        ), patch(
            "app.api.conversations.upsert_message_feedback",
        ) as upsert_feedback:
            response = self.client.post(
                "/chat/messages/42/feedback",
                json={"rating": "positive"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "消息不存在"})
        upsert_feedback.assert_not_called()

    def test_submit_message_feedback_rejects_invalid_reason(self) -> None:
        """反馈原因必须使用受控枚举，避免脏数据扩散。"""
        with patch(
            "app.api.conversations.get_user_assistant_message",
        ) as get_message:
            response = self.client.post(
                "/chat/messages/42/feedback",
                json={"rating": "negative", "reason": "bad_reason"},
            )

        self.assertEqual(response.status_code, 422)
        get_message.assert_not_called()

    def test_submit_message_source_feedback_upserts_existing_source(self) -> None:
        """用户可以标记自己助手消息中的真实引用来源。"""
        with patch(
            "app.api.conversations.get_user_assistant_message",
            return_value={
                "id": 42,
                "role": "assistant",
                "status": "completed",
                "conversation_id": uuid4(),
                "sources": [
                    {
                        "index": 1,
                        "file_id": str(uuid4()),
                        "file_name": "民事诉讼法.pdf",
                        "chunk_index": 2,
                        "retrieval_sources": ["vector", "fulltext"],
                    }
                ],
            },
        ) as get_message, patch(
            "app.api.conversations.upsert_message_source_feedback",
            return_value={
                "id": 11,
                "user_id": 1,
                "message_id": 42,
                "source_index": 1,
                "knowledge_file_id": None,
                "chunk_index": 2,
                "rating": "irrelevant",
                "note": None,
                "metadata": {"file_name": "民事诉讼法.pdf"},
                "created_at": "2026-06-25T00:00:02+08:00",
                "updated_at": "2026-06-25T00:00:03+08:00",
            },
        ) as upsert_feedback:
            response = self.client.post(
                "/chat/messages/42/sources/1/feedback",
                json={"rating": "irrelevant"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["feedback"]["rating"], "irrelevant")
        get_message.assert_called_once_with(1, 42)
        self.assertEqual(upsert_feedback.call_args.kwargs["source_index"], 1)
        self.assertEqual(upsert_feedback.call_args.kwargs["chunk_index"], 2)

    def test_submit_message_source_feedback_returns_404_for_missing_source(
        self,
    ) -> None:
        """source index 不存在时不能写入伪造引用反馈。"""
        with patch(
            "app.api.conversations.get_user_assistant_message",
            return_value={
                "id": 42,
                "role": "assistant",
                "status": "completed",
                "conversation_id": uuid4(),
                "sources": [{"index": 1, "file_name": "民事诉讼法.pdf"}],
            },
        ), patch(
            "app.api.conversations.upsert_message_source_feedback",
        ) as upsert_feedback:
            response = self.client.post(
                "/chat/messages/42/sources/5/feedback",
                json={"rating": "useful"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "引用来源不存在"})
        upsert_feedback.assert_not_called()

    def test_export_message_eval_case_draft_returns_rag_case_shape(self) -> None:
        """差评助手消息应能导出可人工整理的 eval case 草稿。"""
        conversation_id = uuid4()
        knowledge_base_id = uuid4()
        with patch(
            "app.api.conversations.get_user_message_eval_draft_context",
            return_value={
                "message_id": 42,
                "answer": "民事诉讼法的任务是保护当事人诉讼权利。",
                "sources": [
                    {
                        "index": 1,
                        "file_name": "中华人民共和国民事诉讼法_20230901.pdf",
                        "chunk_index": 2,
                    }
                ],
                "retrieval": {
                    "need_retrieval": True,
                    "source_count": 1,
                    "retrieved_count": 5,
                },
                "message_created_at": "2026-06-30T09:00:00+08:00",
                "conversation_id": conversation_id,
                "conversation_title": "诉讼法问答",
                "knowledge_base_id": knowledge_base_id,
                "knowledge_base_name": "默认知识库",
                "question": "民事诉讼法的任务是什么",
                "question_message_id": 41,
                "feedback_rating": "negative",
                "feedback_reason": "missing_answer",
                "feedback_note": "回答不完整",
                "feedback_metadata": {},
            },
        ) as get_context:
            response = self.client.get("/chat/messages/42/eval-case-draft")

        self.assertEqual(response.status_code, 200)
        draft = response.json()["draft"]
        self.assertEqual(draft["id"], "draft_message_42")
        self.assertEqual(draft["question"], "民事诉讼法的任务是什么")
        self.assertTrue(draft["expect_retrieval"])
        self.assertEqual(draft["min_sources"], 1)
        self.assertEqual(
            draft["expected_files"],
            ["中华人民共和国民事诉讼法_20230901.pdf"],
        )
        self.assertEqual(
            draft["draft_metadata"]["feedback"]["reason"],
            "missing_answer",
        )
        get_context.assert_called_once_with(1, 42)

    def test_export_message_eval_case_draft_returns_404_for_inaccessible_message(
        self,
    ) -> None:
        """跨用户或不存在的助手消息不能导出 eval 草稿。"""
        with patch(
            "app.api.conversations.get_user_message_eval_draft_context",
            return_value=None,
        ):
            response = self.client.get("/chat/messages/42/eval-case-draft")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "消息不存在"})

    def test_export_message_eval_case_draft_requires_user_question(self) -> None:
        """缺少对应用户问题时返回业务错误，避免生成不可复现草稿。"""
        with patch(
            "app.api.conversations.get_user_message_eval_draft_context",
            return_value={
                "message_id": 42,
                "answer": "回答",
                "sources": [],
                "retrieval": {},
                "conversation_id": uuid4(),
                "conversation_title": "旧会话",
                "knowledge_base_id": uuid4(),
                "knowledge_base_name": "默认知识库",
                "question": None,
                "question_message_id": None,
                "feedback_rating": None,
                "feedback_reason": None,
                "feedback_note": None,
                "feedback_metadata": {},
            },
        ):
            response = self.client.get("/chat/messages/42/eval-case-draft")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "缺少可导出的用户问题"})

    def test_get_conversation_diagnostics_returns_rag_debug_summary(
        self,
    ) -> None:
        """诊断接口应返回助手消息的检索路径、降级状态和来源预览。"""
        conversation_id = uuid4()
        message_id = uuid4()
        sources = [
            {
                "index": 1,
                "file_id": "file-1",
                "file_name": "民事诉讼法.pdf",
                "chunk_index": 2,
                "retrieval_sources": ["fulltext", "vector"],
                "vector_score": 0.12,
                "fulltext_score": 3.45,
                "rrf_score": 0.03,
                "rerank_score": 5.4,
                "content": "较长正文不需要在诊断摘要中重复返回",
            }
        ]
        retrieval = {
            "need_retrieval": True,
            "final_need_retrieval": True,
            "llm_need_retrieval": False,
            "rewritten_query": "诉讼法的任务是什么",
            "reason": "问题涉及知识库",
            "llm_reason": "模型认为可直接回答",
            "override_applied": True,
            "override_reason": "问题关键词命中当前知识库文件画像，已强制检索",
            "retrieved_count": 5,
            "source_count": 1,
            "retrieval_sources": ["fulltext", "vector"],
            "vector_degraded": False,
            "diagnostics": {
                "vector_count": 5,
                "fulltext_count": 5,
                "fused_count": 5,
                "reranked_count": 5,
                "vector_degraded": False,
                "vector_errors": [],
                "retrieval_sources": ["fulltext", "vector"],
            },
        }
        with patch(
            "app.api.conversations.conversation_exists",
            return_value=True,
        ), patch(
            "app.api.conversations.get_user_conversation_messages",
            return_value=[
                {
                    "id": uuid4(),
                    "role": "user",
                    "content": "诉讼法的任务是什么",
                    "status": "completed",
                    "error_message": None,
                    "sources": [],
                    "retrieval": {},
                    "created_at": "2026-06-25T00:00:00+08:00",
                },
                {
                    "id": message_id,
                    "role": "assistant",
                    "content": "回答",
                    "status": "completed",
                    "error_message": None,
                    "sources": sources,
                    "retrieval": retrieval,
                    "created_at": "2026-06-25T00:00:01+08:00",
                },
            ],
        ):
            response = self.client.get(
                f"/chat/conversations/{conversation_id}/diagnostics",
            )

        self.assertEqual(response.status_code, 200)
        diagnostic = response.json()["diagnostics"][0]
        self.assertEqual(diagnostic["message_id"], str(message_id))
        self.assertEqual(diagnostic["retrieved_count"], 5)
        self.assertEqual(diagnostic["source_count"], 1)
        self.assertTrue(diagnostic["final_need_retrieval"])
        self.assertFalse(diagnostic["llm_need_retrieval"])
        self.assertTrue(diagnostic["override_applied"])
        self.assertIn("知识库文件画像", diagnostic["override_reason"])
        self.assertEqual(diagnostic["retrieval_sources"], ["fulltext", "vector"])
        self.assertFalse(diagnostic["vector_degraded"])
        self.assertEqual(diagnostic["diagnostics"]["vector_count"], 5)
        self.assertNotIn("content", diagnostic["sources_preview"][0])
        self.assertEqual(diagnostic["sources_preview"][0]["chunk_index"], 2)
        self.assertEqual(diagnostic["sources_preview"][0]["vector_score"], 0.12)
        self.assertEqual(
            diagnostic["sources_preview"][0]["fulltext_score"],
            3.45,
        )

    def test_get_diagnostics_returns_404_for_inaccessible_conversation(
        self,
    ) -> None:
        """跨用户或已软删除的会话不应继续读取诊断信息。"""
        conversation_id = uuid4()
        with patch(
            "app.api.conversations.conversation_exists",
            return_value=False,
        ), patch(
            "app.api.conversations.get_user_conversation_messages",
        ) as get_messages:
            response = self.client.get(
                f"/chat/conversations/{conversation_id}/diagnostics",
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "会话不存在"})
        get_messages.assert_not_called()

    def test_rename_returns_404_for_cross_base_conversation(self) -> None:
        """重命名时必须同时校验会话属于当前知识库和用户。"""
        knowledge_base_id = uuid4()
        conversation_id = uuid4()
        with patch(
            "app.api.conversations.conversation_belongs_base",
            return_value=False,
        ), patch(
            "app.api.conversations.rename_conversation_record",
        ) as rename_record:
            response = self.client.patch(
                f"/chat/knowledge-bases/{knowledge_base_id}/conversations/"
                f"{conversation_id}",
                json={"title": "新标题"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "禁止跨知识库提问"})
        rename_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
