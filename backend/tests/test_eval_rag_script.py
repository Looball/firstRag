import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_rag


class EvalRagQualityGateTests(unittest.TestCase):
    """RAG eval 脚本质量门禁测试。"""

    def build_result(
        self,
        *,
        passed: bool = True,
        source_count: int = 1,
        timing: dict | None = None,
        total_tokens: int | None = None,
    ) -> dict:
        """构建最小可用的 eval result。"""
        retrieval = {
            "diagnostics": {
                "timing": timing or {},
                "llm": {},
            },
        }
        if total_tokens is not None:
            retrieval["diagnostics"]["llm"]["total_tokens"] = total_tokens

        return {
            "passed": passed,
            "chat_result": eval_rag.ChatResult(
                answer="answer",
                sources=[{} for _ in range(source_count)],
                retrieval=retrieval,
                message_id="message-id",
                elapsed_seconds=1.5,
            ),
        }

    def test_build_summary_uses_pre_answer_as_first_token_fallback(self):
        """流式 retrieval 未携带 first_answer_token_ms 时应使用 pre_answer_total_ms。"""
        results = [
            self.build_result(
                timing={"pre_answer_total_ms": 1000},
                total_tokens=300,
            ),
            self.build_result(
                timing={
                    "first_answer_token_ms": 500,
                    "pre_answer_total_ms": 700,
                },
                total_tokens=100,
            ),
        ]

        summary = eval_rag.build_summary(results)

        self.assertEqual(summary["average_first_token_ms"], 750)
        self.assertEqual(summary["average_pre_answer_ms"], 850)
        self.assertEqual(summary["average_total_tokens"], 200)

    def test_quality_gate_checks_thresholds(self):
        """质量门禁应按命令行阈值生成通过和失败结果。"""
        args = type("Args", (), {
            "min_pass_rate": 1.0,
            "min_average_sources": 2.0,
            "max_average_first_token_ms": 800.0,
            "max_average_elapsed_seconds": 2.0,
        })()
        summary = {
            "pass_rate": 0.5,
            "average_sources": 2.5,
            "average_first_token_ms": 900.0,
            "average_elapsed_seconds": 1.5,
        }

        checks = eval_rag.build_quality_gate_checks(summary, args)
        results = {check["name"]: check["passed"] for check in checks}

        self.assertFalse(results["min_pass_rate"])
        self.assertTrue(results["min_average_sources"])
        self.assertFalse(results["max_average_first_token_ms"])
        self.assertTrue(results["max_average_elapsed_seconds"])


if __name__ == "__main__":
    unittest.main()
