"""OCR 历史持久化、同环境趋势和降级行为测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from app.services.documents.pdf_ocr_trend import (
    assess_ocr_trend,
    load_ocr_history,
    persist_ocr_history_record,
    render_ocr_trend_markdown,
    update_ocr_history_and_trend,
)


def build_record(
    run_id: str,
    generated_at: str,
    *,
    quality: float = 0.99,
    seconds: float = 10.0,
    runner_os: str = "Linux",
    runner_arch: str = "X64",
    tesseract_version: str = "tesseract 5.5.0",
    benchmark_suite: str = "manifest-v2-current",
    passed: bool = True,
) -> dict[str, object]:
    """构造不包含用户正文的最小 schema v3 历史记录。"""
    return {
        "schema_version": 3,
        "generated_at": generated_at,
        "tesseract_version": tesseract_version,
        "benchmark_suite": benchmark_suite,
        "execution": {
            "runner_os": runner_os,
            "runner_arch": runner_arch,
            "run_id": run_id,
            "run_attempt": "1",
            "commit_sha": f"sha-{run_id}",
            "ref_name": "main",
        },
        "average_adaptive_similarity": quality,
        "total_seconds": seconds,
        "violations": [],
        "passed": passed,
        "cases": [
            {
                "case_id": "clean_latin",
                "adaptive_similarity": quality,
                "elapsed_seconds": seconds,
                "selected_strategy": "baseline_auto",
                "passed": passed,
            },
        ],
    }


class PdfOcrTrendTests(unittest.TestCase):
    """验证历史趋势只比较相同 runtime 且不会污染硬门禁。"""

    def test_trend_uses_only_same_runtime_and_recent_median(self) -> None:
        """其他 OS、Tesseract 或 suite 不得进入当前趋势基线。"""
        records = [
            build_record("1", "2026-07-23T00:00:00+00:00", seconds=10),
            build_record(
                "2",
                "2026-07-23T00:01:00+00:00",
                seconds=100,
                runner_os="macOS",
            ),
            build_record(
                "3",
                "2026-07-23T00:02:00+00:00",
                seconds=90,
                benchmark_suite="manifest-v1-legacy",
            ),
            build_record("4", "2026-07-23T00:03:00+00:00", seconds=11),
        ]

        markdown = render_ocr_trend_markdown(records)

        self.assertIn("Trend status: **STABLE**", markdown)
        self.assertIn("Comparable runs: `2`; baseline window: `1`", markdown)
        self.assertIn("baseline median: `10.000s`", markdown)
        self.assertNotIn("100.000s", markdown)
        self.assertNotIn("90.000s", markdown)

    def test_current_run_remains_anchor_when_cache_has_future_record(self) -> None:
        """异常未来时间戳不能让旧 cache 记录取代本次运行。"""
        current = build_record("1", "2026-07-23T00:00:00+00:00", seconds=10)
        future = build_record("2", "2099-01-01T00:00:00+00:00", seconds=100)

        markdown = render_ocr_trend_markdown(
            [current, future],
            current_record=current,
        )

        self.assertIn("Trend status: **BASELINE**", markdown)
        self.assertIn("Latest total time: `10.000s`", markdown)
        self.assertNotIn("100.000s", markdown)

    def test_assessment_marks_slow_drift_watch_then_regressed(self) -> None:
        """相对最近中位数变慢 25% 提醒，变慢 50% 判为回退。"""
        baseline = [
            build_record(str(index), f"2026-07-23T00:0{index}:00", seconds=10)
            for index in range(1, 4)
        ]

        watched = assess_ocr_trend(
            [
                *baseline,
                build_record("4", "2026-07-23T00:04:00+00:00", seconds=13),
            ],
        )
        regressed = assess_ocr_trend(
            [
                *baseline,
                build_record("5", "2026-07-23T00:05:00+00:00", seconds=15),
            ],
        )

        self.assertEqual(watched["status"], "watch")
        self.assertEqual(watched["time_ratio"], 1.3)
        self.assertEqual(regressed["status"], "regressed")
        self.assertEqual(regressed["time_ratio"], 1.5)

    def test_assessment_marks_quality_drop_and_hard_gate_failure(self) -> None:
        """质量明显下降或当前硬门禁失败都应显示回退。"""
        baseline = build_record("1", "2026-07-23T00:00:00+00:00", quality=1.0)
        quality_drop = build_record(
            "2",
            "2026-07-23T00:01:00+00:00",
            quality=0.97,
        )
        gate_failure = build_record(
            "3",
            "2026-07-23T00:02:00+00:00",
            passed=False,
        )

        self.assertEqual(
            assess_ocr_trend([baseline, quality_drop])["status"],
            "regressed",
        )
        assessment = assess_ocr_trend([baseline, gate_failure])
        self.assertEqual(assessment["status"], "regressed")
        self.assertIn("current OCR hard gate failed", assessment["reasons"])

    def test_loader_ignores_corrupt_and_unsupported_history(self) -> None:
        """单个历史文件损坏不应阻止其余记录形成趋势。"""
        with TemporaryDirectory() as directory:
            history = Path(directory)
            (history / "broken.json").write_text("{", encoding="utf-8")
            (history / "future.json").write_text(
                json.dumps({"schema_version": 999}),
                encoding="utf-8",
            )
            (history / "valid.json").write_text(
                json.dumps(build_record("1", "2026-07-23T00:00:00+00:00")),
                encoding="utf-8",
            )

            records, warnings = load_ocr_history(history)

        self.assertEqual(len(records), 1)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all("ignored" in warning for warning in warnings))

    def test_persistence_deduplicates_rerun_and_prunes_old_records(self) -> None:
        """相同 run/attempt 覆盖，目录总量按时间保留最近记录。"""
        with TemporaryDirectory() as directory:
            history = Path(directory)
            for index in range(1, 4):
                persist_ocr_history_record(
                    build_record(
                        str(index),
                        f"2026-07-23T00:0{index}:00+00:00",
                    ),
                    history,
                    max_records=2,
                )
            persist_ocr_history_record(
                build_record(
                    "3",
                    "2026-07-23T00:03:30+00:00",
                    seconds=12,
                ),
                history,
                max_records=2,
            )
            records, warnings = load_ocr_history(history)

        self.assertEqual(warnings, ())
        self.assertEqual([record["execution"]["run_id"] for record in records], ["2", "3"])
        self.assertEqual(records[-1]["total_seconds"], 12)

    def test_update_writes_bounded_history_and_safe_summary(self) -> None:
        """趋势摘要不会回显历史 JSON 中无关的敏感扩展字段。"""
        payload = build_record("1", "2026-07-23T00:00:00+00:00")
        payload["api_key"] = "must-not-appear"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history_path, warnings = update_ocr_history_and_trend(
                payload,
                root / "history",
                root / "trend.md",
            )
            trend = (root / "trend.md").read_text(encoding="utf-8")
            persisted = history_path.read_text(encoding="utf-8")

        self.assertTrue(history_path.name.startswith("ci-1-1"))
        self.assertEqual(warnings, ())
        self.assertIn("Trend status: **BASELINE**", trend)
        self.assertNotIn("must-not-appear", trend)
        self.assertNotIn("must-not-appear", persisted)


if __name__ == "__main__":
    unittest.main()
