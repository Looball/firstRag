"""合成 PDF OCR 评测集、评分与门禁回归测试。"""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pymupdf

from app.services.documents.pdf_ocr_benchmark import (
    DEFAULT_MANIFEST_PATH,
    OcrBenchmarkAggregate,
    OcrBenchmarkCase,
    OcrBenchmarkConfigError,
    OcrBenchmarkManifest,
    _render_case_image,
    build_ocr_benchmark_suite,
    calculate_ocr_text_similarity,
    evaluate_ocr_benchmark_case,
    generate_ocr_benchmark_pdf,
    load_ocr_benchmark_manifest,
    normalize_ocr_benchmark_text,
    render_ocr_benchmark_markdown,
    run_ocr_benchmark,
    serialize_ocr_benchmark_report,
)
from app.services.documents.pdf_ocr_engine import (
    PdfOcrCandidateSummary,
    PdfOcrResult,
)


def build_case(**overrides: object) -> OcrBenchmarkCase:
    """构造可按字段覆盖的最小 benchmark case。"""
    values: dict[str, object] = {
        "case_id": "sample_case",
        "description": "sample",
        "lines": ("FIRST RAG OCR", "SAMPLE 2026"),
        "rotation": 0,
        "contrast": 1.0,
        "blur_radius": 0.0,
        "min_adaptive_similarity": 0.9,
        "min_improvement": -0.05,
        "allowed_strategies": (),
        "required_candidate_strategies": (),
    }
    values.update(overrides)
    return OcrBenchmarkCase(**values)  # type: ignore[arg-type]


def build_adaptive_result(text: str, strategy: str = "single_block_gray") -> PdfOcrResult:
    """构造满足多候选约束的自适应 OCR 结果。"""
    summaries = (
        PdfOcrCandidateSummary(
            "baseline_auto",
            "color",
            3,
            0,
            "succeeded",
            selected=False,
        ),
        PdfOcrCandidateSummary(
            strategy,
            "grayscale",
            6,
            0,
            "succeeded",
            selected=True,
        ),
    )
    return PdfOcrResult(
        text=text,
        confidence=95.0,
        word_count=4,
        strategy=strategy,
        preprocessing="grayscale",
        psm=6,
        candidate_summaries=summaries,
    )


class PdfOcrBenchmarkTests(unittest.TestCase):
    """验证评测 manifest、样本、评分和失败退出依据。"""

    def test_default_manifest_covers_required_scan_classes(self) -> None:
        """默认清单应覆盖十类独立扫描质量，而非干净大字样本。"""
        manifest = load_ocr_benchmark_manifest(DEFAULT_MANIFEST_PATH)

        self.assertEqual(manifest.schema_version, 2)
        self.assertEqual(len(manifest.cases), 10)
        case_ids = {case.case_id for case in manifest.cases}
        self.assertEqual(
            case_ids,
            {
                "clean_latin",
                "rotated_90_latin",
                "low_contrast_latin",
                "blurred_latin",
                "mixed_chinese_english",
                "skewed_latin",
                "noisy_latin",
                "shadowed_latin",
                "small_font_latin",
                "table_latin",
            },
        )
        rotated_case = next(
            case for case in manifest.cases if case.case_id == "rotated_90_latin"
        )
        self.assertEqual(
            rotated_case.required_candidate_strategies,
            ("rotate_90_gray", "rotate_270_gray"),
        )
        table_case = next(
            case for case in manifest.cases if case.case_id == "table_latin"
        )
        self.assertEqual(table_case.layout, "table")
        self.assertEqual(
            table_case.expected_text.splitlines()[1],
            "VECTOR 16 A102",
        )

    def test_manifest_rejects_duplicate_case_ids(self) -> None:
        """重复 case id 会使历史报告不可比较，必须拒绝。"""
        payload = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        payload["cases"].append(payload["cases"][0])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(OcrBenchmarkConfigError, "case id 重复"):
                load_ocr_benchmark_manifest(path)

    def test_legacy_v1_manifest_remains_loadable(self) -> None:
        """升级默认集后仍应允许显式复跑历史 v1 manifest。"""
        legacy_path = DEFAULT_MANIFEST_PATH.with_name("pdf_ocr_eval_v1.json")

        manifest = load_ocr_benchmark_manifest(legacy_path)

        self.assertEqual(manifest.schema_version, 1)
        self.assertEqual(len(manifest.cases), 5)
        self.assertTrue(all(case.layout == "lines" for case in manifest.cases))

    def test_manifest_rejects_unbounded_or_invalid_degradations(self) -> None:
        """非法 layout、噪点范围和不规则表格必须在生成前拒绝。"""
        original = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        mutations = (
            ("layout", 0, {"layout": "columns"}, "layout"),
            ("noise", 0, {"noise_density": 0.2}, "noise_density"),
            (
                "table",
                9,
                {"table_rows": [["A", "B"], ["C", "D", "E"]]},
                "列数不一致",
            ),
        )
        with TemporaryDirectory() as directory:
            for name, case_index, updates, error in mutations:
                with self.subTest(name=name):
                    payload = json.loads(json.dumps(original))
                    payload["cases"][case_index].update(updates)
                    path = Path(directory) / f"{name}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(OcrBenchmarkConfigError, error):
                        load_ocr_benchmark_manifest(path)

    def test_degraded_image_generation_is_deterministic(self) -> None:
        """同一 case 的噪点、阴影与倾斜输出必须逐字节稳定。"""
        case = build_case(
            skew_degrees=2.5,
            noise_density=0.01,
            shadow_strength=0.4,
        )

        self.assertEqual(_render_case_image(case), _render_case_image(case))

    def test_suite_fingerprint_changes_with_case_parameters(self) -> None:
        """suite fingerprint 应稳定，并在任一退化参数改变时变化。"""
        manifest = load_ocr_benchmark_manifest(DEFAULT_MANIFEST_PATH)
        changed_case = replace(manifest.cases[0], contrast=0.95)
        changed = replace(
            manifest,
            cases=(changed_case, *manifest.cases[1:]),
        )

        self.assertEqual(
            build_ocr_benchmark_suite(manifest),
            build_ocr_benchmark_suite(manifest),
        )
        self.assertNotEqual(
            build_ocr_benchmark_suite(manifest),
            build_ocr_benchmark_suite(changed),
        )

    def test_similarity_normalizes_case_spacing_and_unicode_width(self) -> None:
        """评分应忽略大小写、空白和全角数字差异。"""
        self.assertEqual(
            normalize_ocr_benchmark_text(" First RAG ２０２６\n"),
            "firstrag2026",
        )
        self.assertEqual(
            calculate_ocr_text_similarity("第一 RAG 2026", "第一rag２０２６"),
            1.0,
        )

    def test_generated_pdf_is_single_page_without_text_layer(self) -> None:
        """生成样本必须是真正走 OCR fallback 的图片型 PDF。"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            generate_ocr_benchmark_pdf(build_case(), path)
            document = pymupdf.open(path)
            try:
                self.assertEqual(document.page_count, 1)
                page = document.load_page(0)
                self.assertEqual(page.get_text("text"), "")
                self.assertEqual(len(page.get_images(full=True)), 1)
            finally:
                document.close()

    def test_case_gate_reports_similarity_improvement_and_strategy(self) -> None:
        """单样本应同时检查质量、改善量和允许策略。"""
        case = build_case(
            min_improvement=0.4,
            allowed_strategies=("rotate_90_gray",),
        )
        result = evaluate_ocr_benchmark_case(
            case,
            PdfOcrResult("wrong", 20.0, 1),
            build_adaptive_result(case.expected_text, "single_block_gray"),
            1.25,
        )

        self.assertEqual(result.adaptive_similarity, 1.0)
        self.assertGreater(result.improvement, 0.4)
        self.assertFalse(result.passed)
        self.assertIn("strategy single_block_gray", result.violations[0])

    def test_case_gate_requires_configured_candidate_to_succeed(self) -> None:
        """旋转候选未执行成功时不能只凭最终文本通过门禁。"""
        case = build_case(
            required_candidate_strategies=("rotate_90_gray",),
        )
        result = evaluate_ocr_benchmark_case(
            case,
            PdfOcrResult(case.expected_text, 95.0, 4),
            build_adaptive_result(case.expected_text),
            1.25,
        )

        self.assertFalse(result.passed)
        self.assertIn(
            "required candidate rotate_90_gray did not succeed",
            result.violations,
        )

    def test_run_gate_fails_aggregate_even_when_case_passes(self) -> None:
        """宏平均阈值必须独立于逐样本阈值生效。"""
        case = build_case(min_adaptive_similarity=0.1)
        manifest = OcrBenchmarkManifest(
            schema_version=1,
            aggregate=OcrBenchmarkAggregate(
                min_average_adaptive_similarity=0.99,
                max_total_seconds=180,
            ),
            cases=(case,),
        )
        with TemporaryDirectory() as directory, patch(
            "app.services.documents.pdf_ocr_benchmark.run_pdf_page_ocr",
            side_effect=[
                PdfOcrResult("FIRST", 50.0, 1),
                build_adaptive_result("FIRST RAG OCR SAMPLE"),
            ],
        ):
            report = run_ocr_benchmark(manifest, Path(directory))

        self.assertTrue(report.cases[0].passed)
        self.assertFalse(report.passed)
        self.assertIn("average adaptive similarity", report.violations[0])

    def test_reports_include_machine_and_human_status(self) -> None:
        """JSON 与 Markdown 报告应明确给出通过状态和策略。"""
        case = build_case()
        manifest = OcrBenchmarkManifest(
            schema_version=1,
            aggregate=OcrBenchmarkAggregate(0.5, 180),
            cases=(case,),
        )
        with TemporaryDirectory() as directory, patch(
            "app.services.documents.pdf_ocr_benchmark.run_pdf_page_ocr",
            side_effect=[
                PdfOcrResult(case.expected_text, 90.0, 4),
                build_adaptive_result(case.expected_text),
            ],
        ):
            report = run_ocr_benchmark(manifest, Path(directory))

        payload = serialize_ocr_benchmark_report(report)
        markdown = render_ocr_benchmark_markdown(report)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["schema_version"], 3)
        self.assertTrue(payload["benchmark_suite"].startswith("manifest-v1-"))
        self.assertIsInstance(payload["violations"], list)
        self.assertIsInstance(payload["cases"], list)
        self.assertIsInstance(payload["cases"][0]["violations"], list)
        self.assertTrue(payload["cases"][0]["passed"])
        self.assertIn("Status: **PASS**", markdown)
        self.assertIn("Benchmark suite: `manifest-v1-", markdown)
        self.assertIn("single_block_gray", markdown)


if __name__ == "__main__":
    unittest.main()
