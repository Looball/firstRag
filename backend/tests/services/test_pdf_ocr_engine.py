"""本地 PDF OCR 自适应候选与选优回归测试。"""

from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from app.services.documents.pdf_ocr_engine import (
    BASELINE_OCR_CANDIDATE,
    PdfOcrCandidateSpec,
    PdfOcrError,
    PdfOcrResult,
    build_pdf_ocr_candidate_specs,
    normalize_pdf_ocr_binary_threshold,
    parse_tesseract_tsv_confidence,
    rank_pdf_ocr_candidate,
    run_pdf_page_ocr,
    run_tesseract_candidate,
)


class PdfOcrEngineTests(unittest.TestCase):
    """验证基线成本、自适应容错和确定性选优。"""

    def test_baseline_uses_exactly_one_candidate(self) -> None:
        """普通首次 OCR 不应扩增为多候选。"""
        self.assertEqual(
            build_pdf_ocr_candidate_specs(adaptive=False),
            (BASELINE_OCR_CANDIDATE,),
        )

    def test_adaptive_candidate_count_is_bounded(self) -> None:
        """自适应候选数量必须限制在内置安全集合内。"""
        with patch(
            "app.services.documents.pdf_ocr_engine."
            "PDF_OCR_ADAPTIVE_MAX_CANDIDATES",
            999,
        ):
            candidates = build_pdf_ocr_candidate_specs(adaptive=True)

        self.assertEqual(len(candidates), 6)
        self.assertEqual(
            [candidate.rotation for candidate in candidates[-3:]],
            [90, 180, 270],
        )

    def test_binary_threshold_is_safely_clamped(self) -> None:
        """二值化阈值不能越出单通道像素范围。"""
        self.assertEqual(normalize_pdf_ocr_binary_threshold(-1), 0)
        self.assertEqual(normalize_pdf_ocr_binary_threshold(180), 180)
        self.assertEqual(normalize_pdf_ocr_binary_threshold(999), 255)

    def test_candidate_rank_prefers_usable_higher_confidence_text(self) -> None:
        """有效文本优先，其次比较 confidence 并保持稳定顺序。"""
        low = PdfOcrResult("VALID TEXT", 70.0, 2)
        high = PdfOcrResult("VALID", 88.0, 1)
        empty = PdfOcrResult("", 99.0, 0)

        self.assertGreater(
            rank_pdf_ocr_candidate(high, 1),
            rank_pdf_ocr_candidate(low, 0),
        )
        self.assertGreater(
            rank_pdf_ocr_candidate(low, 0),
            rank_pdf_ocr_candidate(empty, 2),
        )

    def test_adaptive_run_survives_partial_candidate_failure(self) -> None:
        """单个候选失败时应继续采用其他成功候选。"""
        specs = (
            BASELINE_OCR_CANDIDATE,
            PdfOcrCandidateSpec("single_block_gray", "grayscale", 6),
            PdfOcrCandidateSpec("rotate_90_gray", "grayscale", 6, 90),
        )
        baseline = PdfOcrResult(
            "BASELINE TEXT",
            60.0,
            2,
            strategy="baseline_auto",
        )
        rotated = PdfOcrResult(
            "ROTATED BEST TEXT",
            92.0,
            3,
            strategy="rotate_90_gray",
            preprocessing="grayscale",
            psm=6,
            rotation=90,
        )
        with patch(
            "app.services.documents.pdf_ocr_engine."
            "build_pdf_ocr_candidate_specs",
            return_value=specs,
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "render_pdf_ocr_candidate",
            return_value=b"image",
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "run_tesseract_candidate",
            side_effect=[
                baseline,
                PdfOcrError("candidate failed"),
                rotated,
            ],
        ):
            result = run_pdf_page_ocr(Mock(), adaptive=True)

        self.assertEqual(result.strategy, "rotate_90_gray")
        self.assertEqual(result.rotation, 90)
        self.assertEqual(len(result.candidate_summaries), 3)
        self.assertEqual(
            [summary.status for summary in result.candidate_summaries],
            ["succeeded", "failed", "succeeded"],
        )
        self.assertEqual(
            [summary.selected for summary in result.candidate_summaries],
            [False, False, True],
        )
        self.assertIsNotNone(result.candidate_summaries[0].text_sha256)

    def test_adaptive_run_rejects_all_failed_candidates(self) -> None:
        """没有任何成功候选时应返回稳定错误。"""
        with patch(
            "app.services.documents.pdf_ocr_engine."
            "build_pdf_ocr_candidate_specs",
            return_value=(BASELINE_OCR_CANDIDATE,),
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "render_pdf_ocr_candidate",
            return_value=b"image",
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "run_tesseract_candidate",
            side_effect=PdfOcrError("candidate failed"),
        ):
            with self.assertRaisesRegex(PdfOcrError, "所有候选均识别失败"):
                run_pdf_page_ocr(Mock(), adaptive=True)

    def test_adaptive_total_timeout_includes_rendering(self) -> None:
        """候选渲染耗时也必须计入单页自适应总超时。"""
        with patch(
            "app.services.documents.pdf_ocr_engine."
            "PDF_OCR_ADAPTIVE_TIMEOUT_SECONDS",
            1,
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "build_pdf_ocr_candidate_specs",
            return_value=(BASELINE_OCR_CANDIDATE,),
        ), patch(
            "app.services.documents.pdf_ocr_engine."
            "render_pdf_ocr_candidate",
            return_value=b"image",
        ), patch(
            "app.services.documents.pdf_ocr_engine.time.monotonic",
            side_effect=[0.0, 0.0, 2.0, 2.0],
        ), patch(
            "app.services.documents.pdf_ocr_engine.run_tesseract_candidate",
        ) as run_candidate:
            with self.assertRaisesRegex(PdfOcrError, "自适应识别超时"):
                run_pdf_page_ocr(Mock(), adaptive=True)

        run_candidate.assert_not_called()

    def test_tesseract_candidate_uses_server_owned_psm(self) -> None:
        """Tesseract 命令必须使用候选内置 PSM 且不经过 shell。"""
        completed = Mock(returncode=0)
        spec = PdfOcrCandidateSpec("single_block_gray", "grayscale", 6)
        with patch(
            "app.services.documents.pdf_ocr_engine.subprocess.run",
            return_value=completed,
        ) as run_process, patch.object(
            Path,
            "read_text",
            side_effect=[
                "OCR TEXT",
                (
                    "level\tpage_num\tblock_num\tpar_num\tline_num\t"
                    "word_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tOCR\n"
                ),
            ],
        ):
            result = run_tesseract_candidate(
                image_bytes=b"image",
                spec=spec,
                output_base=Path("/tmp/firstrag-t079-candidate"),
                timeout_seconds=12,
            )

        command = run_process.call_args.args[0]
        self.assertEqual(command[command.index("--psm") + 1], "6")
        self.assertFalse(run_process.call_args.kwargs.get("shell", False))
        self.assertEqual(result.confidence, 90.0)

    def test_tesseract_candidate_timeout_is_safe(self) -> None:
        """单候选超时不应泄露临时路径。"""
        with patch(
            "app.services.documents.pdf_ocr_engine.subprocess.run",
            side_effect=subprocess.TimeoutExpired("tesseract", 5),
        ):
            with self.assertRaisesRegex(PdfOcrError, "候选识别超时"):
                run_tesseract_candidate(
                    image_bytes=b"image",
                    spec=BASELINE_OCR_CANDIDATE,
                    output_base=Path("/tmp/private-candidate"),
                    timeout_seconds=5,
                )

    def test_tesseract_confidence_is_weighted_by_word_characters(self) -> None:
        """较长 word 应在页面置信度中获得更高权重。"""
        confidence, word_count = parse_tesseract_tsv_confidence(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
            "left\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t50\tA\n"
            "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t90\tLONG\n"
        )

        self.assertEqual(confidence, 82.0)
        self.assertEqual(word_count, 2)


if __name__ == "__main__":
    unittest.main()
