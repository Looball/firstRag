"""受资源约束的本地 Tesseract OCR 候选生成与自适应选优。"""

import csv
from dataclasses import dataclass, replace
import hashlib
import math
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time
from typing import Any

import pymupdf

from app.core.config import (
    PDF_OCR_ADAPTIVE_MAX_CANDIDATES,
    PDF_OCR_ADAPTIVE_TIMEOUT_SECONDS,
    PDF_OCR_BINARY_THRESHOLD,
    PDF_OCR_DPI,
    PDF_OCR_LANGUAGES,
    PDF_OCR_TIMEOUT_SECONDS,
)


PDF_OCR_CANDIDATE_LIMIT = 6
PDF_OCR_MIN_EFFECTIVE_CHARACTERS = 2
PDF_OCR_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_+./-]+$")


class PdfOcrError(ValueError):
    """扫描 PDF 的本地 OCR 无法安全完成时抛出。"""


@dataclass(frozen=True)
class PdfOcrCandidateSpec:
    """一组由服务端固定构造的安全 Tesseract 候选参数。"""

    strategy: str
    preprocessing: str
    psm: int
    rotation: int = 0


@dataclass(frozen=True)
class PdfOcrCandidateSummary:
    """单个候选的可持久化质量摘要，不保存未选中的完整文本。"""

    strategy: str
    preprocessing: str
    psm: int
    rotation: int
    status: str
    confidence: float | None = None
    word_count: int = 0
    effective_characters: int = 0
    text_sha256: str | None = None
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为适合 JSONB 与 API 返回的普通字典。"""
        return {
            "strategy": self.strategy,
            "preprocessing": self.preprocessing,
            "psm": self.psm,
            "rotation": self.rotation,
            "status": self.status,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "effective_characters": self.effective_characters,
            "text_sha256": self.text_sha256,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class PdfOcrResult:
    """单页最佳 Tesseract 文本、质量、策略和候选摘要。"""

    text: str
    confidence: float | None
    word_count: int
    strategy: str = "baseline_auto"
    preprocessing: str = "color"
    psm: int = 3
    rotation: int = 0
    candidate_summaries: tuple[PdfOcrCandidateSummary, ...] = ()


BASELINE_OCR_CANDIDATE = PdfOcrCandidateSpec(
    strategy="baseline_auto",
    preprocessing="color",
    psm=3,
)
ADAPTIVE_OCR_CANDIDATES = (
    BASELINE_OCR_CANDIDATE,
    PdfOcrCandidateSpec(
        strategy="single_block_gray",
        preprocessing="grayscale",
        psm=6,
    ),
    PdfOcrCandidateSpec(
        strategy="single_block_binary",
        preprocessing="binary",
        psm=6,
    ),
    PdfOcrCandidateSpec(
        strategy="rotate_90_gray",
        preprocessing="grayscale",
        psm=6,
        rotation=90,
    ),
    PdfOcrCandidateSpec(
        strategy="rotate_180_gray",
        preprocessing="grayscale",
        psm=6,
        rotation=180,
    ),
    PdfOcrCandidateSpec(
        strategy="rotate_270_gray",
        preprocessing="grayscale",
        psm=6,
        rotation=270,
    ),
)


def count_effective_text_characters(text: str) -> int:
    """统计可表达正文的字母、数字或 CJK 字符。"""
    return sum(character.isalnum() for character in text)


def normalize_pdf_ocr_dpi(value: int) -> int:
    """将 OCR DPI 限制到兼顾识别质量和内存占用的安全范围。"""
    return min(600, max(72, value))


def normalize_pdf_ocr_binary_threshold(value: int) -> int:
    """把二值化阈值限制在单通道像素范围内。"""
    return min(255, max(0, value))


def normalize_pdf_ocr_candidate_limit(value: int) -> int:
    """限制单页自适应 OCR 的候选数量。"""
    return min(PDF_OCR_CANDIDATE_LIMIT, max(1, value))


def parse_tesseract_tsv_confidence(tsv_text: str) -> tuple[float | None, int]:
    """按有效 word 字符数加权计算 Tesseract 页面置信度。"""
    weighted_confidence = 0.0
    total_character_count = 0
    word_count = 0
    for row in csv.DictReader(tsv_text.splitlines(), delimiter="\t"):
        word_text = str(row.get("text") or "").strip()
        character_count = count_effective_text_characters(word_text)
        if character_count <= 0:
            continue
        try:
            confidence = float(row.get("conf") or "-1")
        except ValueError:
            continue
        if confidence < 0:
            continue
        normalized_confidence = min(100.0, max(0.0, confidence))
        weighted_confidence += normalized_confidence * character_count
        total_character_count += character_count
        word_count += 1

    if total_character_count <= 0:
        return None, 0
    return round(weighted_confidence / total_character_count, 2), word_count


def validate_pdf_ocr_runtime_config(adaptive: bool = False) -> None:
    """校验不会传入 shell 的 Tesseract 语言与资源限制配置。"""
    if not PDF_OCR_LANGUAGE_PATTERN.fullmatch(PDF_OCR_LANGUAGES):
        raise PdfOcrError("PDF OCR 语言配置无效")
    if PDF_OCR_TIMEOUT_SECONDS <= 0:
        raise PdfOcrError("PDF OCR 单页超时必须大于 0 秒")
    if adaptive and PDF_OCR_ADAPTIVE_TIMEOUT_SECONDS <= 0:
        raise PdfOcrError("PDF OCR 自适应总超时必须大于 0 秒")


def build_pdf_ocr_candidate_specs(adaptive: bool) -> tuple[PdfOcrCandidateSpec, ...]:
    """返回基线或受配置上限约束的自适应候选序列。"""
    if not adaptive:
        return (BASELINE_OCR_CANDIDATE,)
    limit = normalize_pdf_ocr_candidate_limit(PDF_OCR_ADAPTIVE_MAX_CANDIDATES)
    return ADAPTIVE_OCR_CANDIDATES[:limit]


def _extract_grayscale_samples(pixmap: pymupdf.Pixmap) -> bytes:
    """把可能带 stride 的灰度 Pixmap 规范化为紧凑像素序列。"""
    samples = pixmap.samples
    expected_length = pixmap.width * pixmap.height
    if len(samples) == expected_length:
        return samples
    if pixmap.stride < pixmap.width:
        raise PdfOcrError("PDF OCR 灰度图像数据无效")
    return b"".join(
        samples[row * pixmap.stride:row * pixmap.stride + pixmap.width]
        for row in range(pixmap.height)
    )


def render_pdf_ocr_candidate(
    page: pymupdf.Page,
    spec: PdfOcrCandidateSpec,
    dpi: int,
) -> bytes:
    """按候选 preprocessing 与 rotation 渲染 Tesseract 输入图像。"""
    scale = dpi / 72
    matrix = pymupdf.Matrix(scale, scale).prerotate(spec.rotation)
    if spec.preprocessing == "color":
        pixmap = page.get_pixmap(
            matrix=matrix,
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
        return pixmap.tobytes("png")

    pixmap = page.get_pixmap(
        matrix=matrix,
        colorspace=pymupdf.csGRAY,
        alpha=False,
    )
    if spec.preprocessing == "grayscale":
        return pixmap.tobytes("png")
    if spec.preprocessing != "binary":
        raise PdfOcrError("PDF OCR 预处理策略无效")

    threshold = normalize_pdf_ocr_binary_threshold(PDF_OCR_BINARY_THRESHOLD)
    translation = bytes(255 if value >= threshold else 0 for value in range(256))
    binary_samples = _extract_grayscale_samples(pixmap).translate(translation)
    header = f"P5\n{pixmap.width} {pixmap.height}\n255\n".encode("ascii")
    return header + binary_samples


def run_tesseract_candidate(
    image_bytes: bytes,
    spec: PdfOcrCandidateSpec,
    output_base: Path,
    timeout_seconds: int,
) -> PdfOcrResult:
    """运行一个 Tesseract 候选并读取正文与 TSV quality。"""
    command = [
        "tesseract",
        "stdin",
        str(output_base),
        "-l",
        PDF_OCR_LANGUAGES,
        "--dpi",
        str(normalize_pdf_ocr_dpi(PDF_OCR_DPI)),
        "--psm",
        str(spec.psm),
        "txt",
        "tsv",
    ]
    try:
        completed = subprocess.run(
            command,
            input=image_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise PdfOcrError("PDF OCR 引擎不可用，请安装 Tesseract") from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfOcrError("PDF OCR 候选识别超时") from exc
    except OSError as exc:
        raise PdfOcrError("PDF OCR 无法启动本地识别引擎") from exc

    if completed.returncode != 0:
        raise PdfOcrError("PDF OCR 候选识别失败")
    try:
        text = output_base.with_suffix(".txt").read_text(
            encoding="utf-8",
        ).strip()
        tsv_text = output_base.with_suffix(".tsv").read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise PdfOcrError("PDF OCR 结果读取失败") from exc

    confidence, word_count = parse_tesseract_tsv_confidence(tsv_text)
    return PdfOcrResult(
        text=text,
        confidence=confidence,
        word_count=word_count,
        strategy=spec.strategy,
        preprocessing=spec.preprocessing,
        psm=spec.psm,
        rotation=spec.rotation,
    )


def build_pdf_ocr_candidate_summary(
    spec: PdfOcrCandidateSpec,
    result: PdfOcrResult | None,
    status: str,
) -> PdfOcrCandidateSummary:
    """构造不含未选中文本的候选摘要。"""
    if result is None:
        return PdfOcrCandidateSummary(
            strategy=spec.strategy,
            preprocessing=spec.preprocessing,
            psm=spec.psm,
            rotation=spec.rotation,
            status=status,
        )
    return PdfOcrCandidateSummary(
        strategy=spec.strategy,
        preprocessing=spec.preprocessing,
        psm=spec.psm,
        rotation=spec.rotation,
        status=status,
        confidence=result.confidence,
        word_count=result.word_count,
        effective_characters=count_effective_text_characters(result.text),
        text_sha256=hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
    )


def rank_pdf_ocr_candidate(
    result: PdfOcrResult,
    candidate_index: int,
) -> tuple[int, float, int, int, int]:
    """以有效文本、confidence、字符数和稳定顺序生成确定性排名。"""
    effective_characters = count_effective_text_characters(result.text)
    usable_text = int(effective_characters >= PDF_OCR_MIN_EFFECTIVE_CHARACTERS)
    confidence = result.confidence if result.confidence is not None else -1.0
    return (
        usable_text,
        confidence,
        effective_characters,
        result.word_count,
        -candidate_index,
    )


def select_best_pdf_ocr_candidate(
    results: list[tuple[int, PdfOcrResult]],
) -> tuple[int, PdfOcrResult]:
    """从成功候选中选择确定性的最佳 OCR 结果。"""
    if not results:
        raise PdfOcrError("PDF OCR 所有候选均识别失败")
    return max(
        results,
        key=lambda item: rank_pdf_ocr_candidate(item[1], item[0]),
    )


def run_pdf_page_ocr(
    page: pymupdf.Page,
    *,
    adaptive: bool = False,
) -> PdfOcrResult:
    """执行单页基线 OCR，或在总超时内比较自适应候选并采用最佳结果。"""
    validate_pdf_ocr_runtime_config(adaptive=adaptive)
    specs = build_pdf_ocr_candidate_specs(adaptive)
    dpi = normalize_pdf_ocr_dpi(PDF_OCR_DPI)
    total_timeout = (
        PDF_OCR_ADAPTIVE_TIMEOUT_SECONDS
        if adaptive
        else PDF_OCR_TIMEOUT_SECONDS
    )
    deadline = time.monotonic() + total_timeout
    summaries: list[PdfOcrCandidateSummary] = []
    successful_results: list[tuple[int, PdfOcrResult]] = []

    with TemporaryDirectory(prefix="firstrag-ocr-") as temporary_directory:
        output_directory = Path(temporary_directory)
        for index, spec in enumerate(specs):
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                summaries.extend(
                    build_pdf_ocr_candidate_summary(
                        skipped_spec,
                        None,
                        "skipped",
                    )
                    for skipped_spec in specs[index:]
                )
                break
            try:
                image_bytes = render_pdf_ocr_candidate(page, spec, dpi)
                remaining_seconds = deadline - time.monotonic()
                if remaining_seconds <= 0:
                    summaries.extend(
                        build_pdf_ocr_candidate_summary(
                            skipped_spec,
                            None,
                            "skipped",
                        )
                        for skipped_spec in specs[index:]
                    )
                    break
                candidate_timeout = max(
                    1,
                    min(
                        PDF_OCR_TIMEOUT_SECONDS,
                        math.ceil(remaining_seconds),
                    ),
                )
                result = run_tesseract_candidate(
                    image_bytes=image_bytes,
                    spec=spec,
                    output_base=output_directory / f"candidate-{index}",
                    timeout_seconds=candidate_timeout,
                )
            except PdfOcrError as exc:
                if not adaptive or "引擎不可用" in str(exc):
                    raise
                summaries.append(
                    build_pdf_ocr_candidate_summary(spec, None, "failed"),
                )
                continue
            summaries.append(
                build_pdf_ocr_candidate_summary(spec, result, "succeeded"),
            )
            successful_results.append((index, result))

    if not successful_results:
        if time.monotonic() >= deadline:
            raise PdfOcrError("PDF OCR 自适应识别超时")
        raise PdfOcrError("PDF OCR 所有候选均识别失败")

    selected_index, selected_result = select_best_pdf_ocr_candidate(
        successful_results,
    )
    selected_summaries = tuple(
        replace(summary, selected=index == selected_index)
        for index, summary in enumerate(summaries)
    )
    return replace(
        selected_result,
        candidate_summaries=selected_summaries,
    )
