"""结构化日志脱敏与错误分类的回归测试。"""

import json
import logging
import unittest

from app.core.observability import (
    build_log_event,
    classify_exception,
    log_exception_event,
    set_request_context,
    reset_request_context,
)


class ObservabilityTests(unittest.TestCase):
    """验证 observability helper 的安全边界。"""

    def test_build_log_event_redacts_sensitive_fields_but_keeps_metrics(
        self,
    ) -> None:
        """敏感字段应脱敏，token usage 等指标字段不能被误伤。"""
        event = build_log_event(
            "demo_event",
            api_key="test-secret",
            database_url="postgresql://user:pass@localhost/db",
            nested={
                "authorization": "Bearer abc.def",
                "prompt_tokens": 12,
                "total_tokens": 15,
                "message": "provider rejected api_key=test-secret",
                "redis_error": "redis://:redis-secret@localhost:6379/0",
            },
        )

        payload = json.dumps(event, ensure_ascii=False)

        self.assertNotIn("test-secret", payload)
        self.assertNotIn("user:pass", payload)
        self.assertNotIn("redis-secret", payload)
        self.assertEqual(event["api_key"], "[已脱敏]")
        self.assertEqual(event["nested"]["authorization"], "[已脱敏]")
        self.assertEqual(event["nested"]["prompt_tokens"], 12)
        self.assertEqual(event["nested"]["total_tokens"], 15)

    def test_build_log_event_includes_request_context(self) -> None:
        """请求上下文应自动进入结构化日志事件。"""
        token = set_request_context(request_id="req-1")
        try:
            event = build_log_event("demo_event", user_id=7)
        finally:
            reset_request_context(token)

        self.assertEqual(event["request_id"], "req-1")
        self.assertEqual(event["user_id"], 7)

    def test_classify_exception_distinguishes_common_sources(self) -> None:
        """常见生产错误应落入稳定的错误来源分类。"""
        cases = [
            (RuntimeError("OpenAI provider timeout"), "llm_provider"),
            (RuntimeError("Chroma HNSW Error finding id"), "vector_store"),
            (RuntimeError("psycopg database timeout"), "postgres"),
            (RuntimeError("CrossEncoder rerank failed"), "rerank"),
            (RuntimeError("Zhipu embedding failed"), "embedding"),
            (RuntimeError("Redis ping timeout"), "redis"),
            (FileNotFoundError("missing upload"), "file_storage"),
        ]

        for exc, expected_source in cases:
            with self.subTest(expected_source=expected_source):
                self.assertEqual(
                    classify_exception(exc)["error_source"],
                    expected_source,
                )

    def test_exception_log_redacts_secret_like_text(self) -> None:
        """异常日志 JSON 消息不应包含 API Key 或数据库密码。"""
        logger = logging.getLogger("tests.observability")

        with self.assertLogs("tests.observability", level="ERROR") as logs:
            try:
                raise RuntimeError(
                    "OpenAI failed api_key=test-secret "
                    "postgresql://user:pass@localhost/db",
                )
            except RuntimeError as exc:
                log_exception_event(
                    logger,
                    "demo_failed",
                    exc,
                    default_source="llm_provider",
                )

        output = "\n".join(logs.output)
        self.assertIn("demo_failed", output)
        self.assertIn("llm_provider", output)
        self.assertNotIn("test-secret", output)
        self.assertNotIn("user:pass", output)


if __name__ == "__main__":
    unittest.main()
