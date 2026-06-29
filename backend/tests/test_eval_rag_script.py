import sys
import tempfile
import unittest
from datetime import datetime
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
        diagnostics: dict | None = None,
    ) -> dict:
        """构建最小可用的 eval result。"""
        retrieval = {
            "diagnostics": {
                "timing": timing or {},
                "llm": {},
            },
        }
        if diagnostics:
            retrieval["diagnostics"].update(diagnostics)
        if total_tokens is not None:
            retrieval["diagnostics"]["llm"]["total_tokens"] = total_tokens

        return {
            "case": {
                "id": "case-id",
                "question": "测试问题",
            },
            "passed": passed,
            "chat_result": eval_rag.ChatResult(
                answer="answer",
                sources=[{} for _ in range(source_count)],
                retrieval=retrieval,
                message_id="message-id",
                elapsed_seconds=1.5,
            ),
            "checks": [],
        }

    def test_build_summary_uses_pre_answer_as_first_token_fallback(self):
        """流式 retrieval 未携带 first_answer_token_ms 时应使用 pre_answer_total_ms。"""
        results = [
            self.build_result(
                timing={"pre_answer_total_ms": 1000},
                total_tokens=300,
                diagnostics={"knowledge_profile_cache_hit": False},
            ),
            self.build_result(
                timing={
                    "first_answer_token_ms": 500,
                    "pre_answer_total_ms": 700,
                    "retrieval_settings_ms": 10,
                    "retrieval_settings_load_total_ms": 3,
                    "retrieval_settings_query_ms": 2,
                    "retrieval_settings_normalize_ms": 1,
                    "knowledge_profile_ms": 20,
                    "query_router_ms": 30,
                    "retrieve_documents_ms": 40,
                    "retrieval_total_ms": 50,
                    "rerank_ms": 60,
                },
                total_tokens=100,
                diagnostics={"knowledge_profile_cache_hit": True},
            ),
        ]

        summary = eval_rag.build_summary(results)

        self.assertEqual(summary["average_first_token_ms"], 750)
        self.assertEqual(summary["average_pre_answer_ms"], 850)
        self.assertEqual(summary["average_retrieval_settings_ms"], 10)
        self.assertEqual(summary["average_retrieval_settings_load_total_ms"], 3)
        self.assertEqual(summary["average_retrieval_settings_query_ms"], 2)
        self.assertEqual(
            summary["average_retrieval_settings_normalize_ms"],
            1,
        )
        self.assertEqual(summary["average_knowledge_profile_ms"], 20)
        self.assertEqual(summary["average_query_router_ms"], 30)
        self.assertEqual(summary["average_retrieve_documents_ms"], 40)
        self.assertEqual(summary["average_retrieval_total_ms"], 50)
        self.assertEqual(summary["average_rerank_ms"], 60)
        self.assertEqual(summary["knowledge_profile_cache_hit_count"], 1)
        self.assertEqual(summary["knowledge_profile_cache_observed_count"], 2)
        self.assertEqual(summary["knowledge_profile_cache_hit_rate"], 0.5)
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

    def test_evaluate_case_checks_reason_and_diagnostics(self):
        """case 可声明路由原因和 diagnostics 点路径期望。"""
        chat_result = eval_rag.ChatResult(
            answer="answer",
            sources=[],
            retrieval={
                "need_retrieval": False,
                "final_need_retrieval": False,
                "reason": "当前知识库设置为永不检索",
                "diagnostics": {
                    "settings": {
                        "retrieval_mode": "never",
                        "enable_rerank": False,
                    },
                    "reranked_count": 0,
                    "timing": {},
                    "llm": {},
                },
            },
            message_id="message-id",
            elapsed_seconds=1.0,
        )

        result = eval_rag.evaluate_case(
            {
                "id": "never_mode",
                "question": "测试",
                "expect_retrieval": False,
                "expected_reason_keywords": ["永不检索"],
                "expected_diagnostics": {
                    "settings.retrieval_mode": "never",
                    "settings.enable_rerank": False,
                    "reranked_count": 0,
                },
            },
            chat_result,
        )

        self.assertTrue(result["passed"])

    def test_write_report_includes_stage_timing_table(self):
        """Markdown 报告应展示阶段耗时和 knowledge profile 缓存命中。"""
        result = self.build_result(
            timing={
                "pre_answer_total_ms": 100,
                "retrieval_settings_ms": 2,
                "retrieval_settings_load_total_ms": 0.8,
                "retrieval_settings_query_ms": 0.6,
                "retrieval_settings_normalize_ms": 0.1,
                "knowledge_profile_ms": 3,
                "query_router_ms": 4,
                "retrieve_documents_ms": 5,
                "retrieval_total_ms": 6,
                "rerank_ms": 7,
            },
            diagnostics={
                "knowledge_profile_cache_hit": True,
                "knowledge_profile_indexed_file_count": 2,
                "knowledge_profile_total_file_count": 3,
                "vector_count": 10,
                "fulltext_count": 8,
                "fused_count": 5,
                "reranked_count": 5,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            eval_rag.write_report(
                [result],
                report_path=report_path,
                generated_at=datetime(2026, 6, 28, 12, 0, 0),
            )
            report = report_path.read_text(encoding="utf-8")

        self.assertIn("## 阶段耗时摘要", report)
        self.assertIn(
            "| case-id | 100 | 2 | 0.80 | 0.60 | 0.10 | 3 | 是 | 4 | 5 | 6 | 7 |",
            report,
        )
        self.assertIn(
            "settings 子阶段：load=0.80ms，query=0.60ms，normalize=0.10ms",
            report,
        )
        self.assertIn("knowledge profile 缓存命中：1/1", report)
        self.assertIn("知识库画像缓存：hit=是，indexed_files=2，total_files=3", report)


if __name__ == "__main__":
    unittest.main()
