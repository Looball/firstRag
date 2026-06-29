import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_summary


class EvalSummaryScriptTests(unittest.TestCase):
    """Eval 趋势摘要脚本测试。"""

    def test_build_report_summarizes_rag_and_indexing_history(self) -> None:
        """趋势报告应汇总 RAG 和 indexing 历史指标。"""
        rag_records = [
            {
                "generated_at": "2026-06-28T08:00:00",
                "summary": {
                    "total": 2,
                    "passed": 1,
                    "pass_rate": 0.5,
                    "average_elapsed_seconds": 4.0,
                    "average_sources": 1.0,
                    "average_first_token_ms": 1000.0,
                    "average_total_tokens": 200.0,
                    "average_retrieval_settings_ms": 30.0,
                    "average_knowledge_profile_ms": 40.0,
                    "average_retrieve_documents_ms": 500.0,
                    "average_retrieval_total_ms": 450.0,
                    "average_rerank_ms": 80.0,
                },
                "quality_gate": {"passed": False},
            },
            {
                "generated_at": "2026-06-28T09:00:00",
                "summary": {
                    "total": 2,
                    "passed": 2,
                    "pass_rate": 1.0,
                    "average_elapsed_seconds": 3.0,
                    "average_sources": 2.0,
                    "average_first_token_ms": 800.0,
                    "average_total_tokens": 180.0,
                    "average_retrieval_settings_ms": 10.0,
                    "average_knowledge_profile_ms": 20.0,
                    "average_retrieve_documents_ms": 300.0,
                    "average_retrieval_total_ms": 250.0,
                    "average_rerank_ms": 60.0,
                },
                "quality_gate": {"passed": True},
            },
        ]
        indexing_records = [
            {
                "generated_at": "2026-06-28T09:10:00",
                "passed": True,
                "job": {"status": "succeeded"},
                "chat": {
                    "elapsed_seconds": 2.5,
                    "diagnostics": {
                        "source_count": 1,
                        "vector_degraded": False,
                    },
                },
                "cleanup_done": True,
            }
        ]

        report = eval_summary.build_report(
            rag_records,
            indexing_records,
            limit=10,
        )

        self.assertIn("| 平均通过率 | 0.75 |", report)
        self.assertIn("| 2026-06-28T09:00:00 | 2/2 | 1.00", report)
        self.assertIn("## RAG 阶段耗时趋势", report)
        self.assertIn(
            "| settings | 10.00ms | 20.00ms | -20.00 | <= 1000.00ms | 通过 |",
            report,
        )
        self.assertIn(
            "| hybrid | 250.00ms | 350.00ms | -200.00 | <= 3000.00ms | 通过 |",
            report,
        )
        self.assertIn("| 通过次数 | 1/1 |", report)
        self.assertIn("| 2026-06-28T09:10:00 | 通过 | succeeded", report)
        self.assertIn("-200.00", report)

    def test_summary_report_does_not_include_sensitive_fields(self) -> None:
        """趋势报告不应输出历史 JSON 中的敏感字段。"""
        report = eval_summary.build_report(
            [
                {
                    "generated_at": "2026-06-28T08:00:00",
                    "base_url": "http://127.0.0.1:8000",
                    "username": "MonkeyBing",
                    "password": "123456",
                    "summary": {
                        "total": 1,
                        "passed": 1,
                        "pass_rate": 1.0,
                        "average_elapsed_seconds": 1.0,
                        "average_sources": 1.0,
                    },
                    "quality_gate": {"passed": True},
                }
            ],
            [],
            limit=10,
        )

        self.assertNotIn("MonkeyBing", report)
        self.assertNotIn("123456", report)
        self.assertNotIn("127.0.0.1:8000", report)

    def test_load_json_runs_orders_by_generated_at(self) -> None:
        """读取历史记录时应按 generated_at 排序。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            (runs_dir / "b.json").write_text(
                '{"generated_at": "2026-06-28T09:00:00"}',
                encoding="utf-8",
            )
            (runs_dir / "a.json").write_text(
                '{"generated_at": "2026-06-28T08:00:00"}',
                encoding="utf-8",
            )

            records = eval_summary.load_json_runs(runs_dir)

        self.assertEqual(
            [record["generated_at"] for record in records],
            ["2026-06-28T08:00:00", "2026-06-28T09:00:00"],
        )


if __name__ == "__main__":
    unittest.main()
