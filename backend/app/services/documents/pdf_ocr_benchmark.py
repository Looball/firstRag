"""生成合成扫描 PDF，并用生产 OCR engine 执行可重复质量回归。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from io import BytesIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import time
from typing import Any, Sequence
import unicodedata

from PIL import Image, ImageEnhance, ImageFilter
import pymupdf

from app.services.documents.pdf_ocr_engine import PdfOcrResult, run_pdf_page_ocr


DEFAULT_MANIFEST_PATH = (
    Path(__file__).with_name("fixtures") / "pdf_ocr_eval_v1.json"
)
DEFAULT_JSON_REPORT_PATH = Path("docs/evals/latest_pdf_ocr_eval_report.json")
DEFAULT_MARKDOWN_REPORT_PATH = Path("docs/evals/latest_pdf_ocr_eval_report.md")
OCR_BENCHMARK_SCHEMA_VERSION = 1


class OcrBenchmarkConfigError(ValueError):
    """OCR benchmark manifest 不完整或越出安全范围时抛出。"""


@dataclass(frozen=True)
class OcrBenchmarkCase:
    """一个可确定性生成的 OCR 评测场景。"""

    case_id: str
    description: str
    lines: tuple[str, ...]
    rotation: int
    contrast: float
    blur_radius: float
    min_adaptive_similarity: float
    min_improvement: float
    allowed_strategies: tuple[str, ...]
    required_candidate_strategies: tuple[str, ...]

    @property
    def expected_text(self) -> str:
        """返回用于相似度比较的完整期望正文。"""
        return "\n".join(self.lines)


@dataclass(frozen=True)
class OcrBenchmarkAggregate:
    """跨全部样本的宏平均质量与耗时门禁。"""

    min_average_adaptive_similarity: float
    max_total_seconds: float


@dataclass(frozen=True)
class OcrBenchmarkManifest:
    """经过完整校验的版本化 OCR 评测清单。"""

    schema_version: int
    aggregate: OcrBenchmarkAggregate
    cases: tuple[OcrBenchmarkCase, ...]


@dataclass(frozen=True)
class OcrBenchmarkCaseResult:
    """单个样本的基线、自适应结果和门禁结论。"""

    case_id: str
    description: str
    expected_text: str
    baseline_text: str
    adaptive_text: str
    baseline_similarity: float
    adaptive_similarity: float
    improvement: float
    adaptive_confidence: float | None
    selected_strategy: str
    selected_psm: int
    selected_rotation: int
    candidate_count: int
    elapsed_seconds: float
    violations: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """返回该样本是否满足全部独立阈值。"""
        return not self.violations


@dataclass(frozen=True)
class OcrBenchmarkReport:
    """整次 OCR benchmark 的机器可读结果。"""

    schema_version: int
    generated_at: str
    tesseract_version: str
    average_adaptive_similarity: float
    total_seconds: float
    violations: tuple[str, ...]
    cases: tuple[OcrBenchmarkCaseResult, ...]

    @property
    def passed(self) -> bool:
        """返回逐样本和聚合门禁是否全部通过。"""
        return not self.violations and all(case.passed for case in self.cases)


def _read_float(
    value: object,
    field_name: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    """读取有限范围浮点数并返回可理解的配置错误。"""
    if isinstance(value, bool):
        raise OcrBenchmarkConfigError(f"{field_name} 必须是数字")
    try:
        normalized = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise OcrBenchmarkConfigError(f"{field_name} 必须是数字") from exc
    if not minimum <= normalized <= maximum:
        raise OcrBenchmarkConfigError(
            f"{field_name} 必须位于 {minimum} 到 {maximum} 之间",
        )
    return normalized


def load_ocr_benchmark_manifest(path: Path) -> OcrBenchmarkManifest:
    """加载并严格校验 OCR benchmark manifest。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OcrBenchmarkConfigError("无法读取 OCR benchmark manifest") from exc
    except json.JSONDecodeError as exc:
        raise OcrBenchmarkConfigError("OCR benchmark manifest 不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise OcrBenchmarkConfigError("OCR benchmark manifest 顶层必须是对象")
    if payload.get("schema_version") != OCR_BENCHMARK_SCHEMA_VERSION:
        raise OcrBenchmarkConfigError("OCR benchmark manifest schema version 不受支持")

    aggregate_payload = payload.get("aggregate")
    if not isinstance(aggregate_payload, dict):
        raise OcrBenchmarkConfigError("OCR benchmark aggregate 缺失")
    aggregate = OcrBenchmarkAggregate(
        min_average_adaptive_similarity=_read_float(
            aggregate_payload.get("min_average_adaptive_similarity"),
            "aggregate.min_average_adaptive_similarity",
            minimum=0,
            maximum=1,
        ),
        max_total_seconds=_read_float(
            aggregate_payload.get("max_total_seconds"),
            "aggregate.max_total_seconds",
            minimum=1,
            maximum=900,
        ),
    )

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise OcrBenchmarkConfigError("OCR benchmark 至少需要一个 case")
    if len(raw_cases) > 20:
        raise OcrBenchmarkConfigError("OCR benchmark case 数量不能超过 20")

    cases: list[OcrBenchmarkCase] = []
    case_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise OcrBenchmarkConfigError(f"cases[{index}] 必须是对象")
        case_id = str(raw_case.get("id") or "").strip()
        if not case_id or len(case_id) > 64 or not case_id.replace("_", "").isalnum():
            raise OcrBenchmarkConfigError(f"cases[{index}].id 无效")
        if case_id in case_ids:
            raise OcrBenchmarkConfigError(f"OCR benchmark case id 重复：{case_id}")
        case_ids.add(case_id)
        raw_lines = raw_case.get("lines")
        if (
            not isinstance(raw_lines, list)
            or not raw_lines
            or len(raw_lines) > 6
            or any(not isinstance(line, str) or not line.strip() for line in raw_lines)
        ):
            raise OcrBenchmarkConfigError(f"cases[{index}].lines 无效")
        if any(len(line) > 80 for line in raw_lines):
            raise OcrBenchmarkConfigError(f"cases[{index}].lines 单行过长")
        rotation = raw_case.get("rotation")
        if isinstance(rotation, bool) or rotation not in {0, 90, 180, 270}:
            raise OcrBenchmarkConfigError(f"cases[{index}].rotation 无效")
        raw_strategies = raw_case.get("allowed_strategies", [])
        if not isinstance(raw_strategies, list) or any(
            not isinstance(strategy, str) or not strategy
            for strategy in raw_strategies
        ):
            raise OcrBenchmarkConfigError(
                f"cases[{index}].allowed_strategies 无效",
            )
        raw_required_strategies = raw_case.get(
            "required_candidate_strategies",
            [],
        )
        if not isinstance(raw_required_strategies, list) or any(
            not isinstance(strategy, str) or not strategy
            for strategy in raw_required_strategies
        ):
            raise OcrBenchmarkConfigError(
                f"cases[{index}].required_candidate_strategies 无效",
            )
        cases.append(OcrBenchmarkCase(
            case_id=case_id,
            description=str(raw_case.get("description") or case_id)[:200],
            lines=tuple(line.strip() for line in raw_lines),
            rotation=int(rotation),
            contrast=_read_float(
                raw_case.get("contrast"),
                f"cases[{index}].contrast",
                minimum=0.05,
                maximum=2,
            ),
            blur_radius=_read_float(
                raw_case.get("blur_radius"),
                f"cases[{index}].blur_radius",
                minimum=0,
                maximum=5,
            ),
            min_adaptive_similarity=_read_float(
                raw_case.get("min_adaptive_similarity"),
                f"cases[{index}].min_adaptive_similarity",
                minimum=0,
                maximum=1,
            ),
            min_improvement=_read_float(
                raw_case.get("min_improvement"),
                f"cases[{index}].min_improvement",
                minimum=-1,
                maximum=1,
            ),
            allowed_strategies=tuple(raw_strategies),
            required_candidate_strategies=tuple(raw_required_strategies),
        ))
    return OcrBenchmarkManifest(
        schema_version=OCR_BENCHMARK_SCHEMA_VERSION,
        aggregate=aggregate,
        cases=tuple(cases),
    )


def normalize_ocr_benchmark_text(text: str) -> str:
    """以 Unicode NFKC、casefold 和字母数字字符规范化 OCR 文本。"""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def calculate_ocr_text_similarity(expected: str, actual: str) -> float:
    """返回 0 到 1 的规范化字符序列相似度。"""
    normalized_expected = normalize_ocr_benchmark_text(expected)
    normalized_actual = normalize_ocr_benchmark_text(actual)
    if not normalized_expected:
        return 1.0 if not normalized_actual else 0.0
    return round(
        SequenceMatcher(None, normalized_expected, normalized_actual).ratio(),
        4,
    )


def _render_case_image(case: OcrBenchmarkCase) -> bytes:
    """用嵌入式 CJK 字体生成测试文字并施加确定性图像退化。"""
    source = pymupdf.open()
    try:
        page = source.new_page(width=760, height=430)
        for line_index, line in enumerate(case.lines):
            font_name = (
                "china-s"
                if any(ord(character) > 127 for character in line)
                else "helv"
            )
            page.insert_text(
                (58, 125 + line_index * 82),
                line,
                fontname=font_name,
                fontsize=40 if font_name == "helv" else 37,
                color=(0, 0, 0),
            )
        image_bytes = page.get_pixmap(dpi=180, alpha=False).tobytes("png")
    finally:
        source.close()
    with Image.open(BytesIO(image_bytes)) as raw_image:
        image = raw_image.convert("RGB")
        if case.contrast != 1:
            image = ImageEnhance.Contrast(image).enhance(case.contrast)
        if case.blur_radius > 0:
            image = image.filter(ImageFilter.GaussianBlur(radius=case.blur_radius))
        if case.rotation:
            image = image.rotate(-case.rotation, expand=True, fillcolor="white")
        output = BytesIO()
        image.save(output, format="PNG", optimize=False)
        return output.getvalue()


def generate_ocr_benchmark_pdf(case: OcrBenchmarkCase, output_path: Path) -> None:
    """生成无文本层的单页图片型 PDF benchmark 样本。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    try:
        page = document.new_page(width=595, height=842)
        page.insert_image(
            page.rect,
            stream=_render_case_image(case),
            keep_proportion=True,
        )
        document.save(output_path, deflate=True, garbage=4)
    finally:
        document.close()

    verification = pymupdf.open(output_path)
    try:
        if verification.page_count != 1:
            raise OcrBenchmarkConfigError("OCR benchmark PDF 必须恰好包含一页")
        if verification.load_page(0).get_text("text").strip():
            raise OcrBenchmarkConfigError("OCR benchmark PDF 不能包含原生文本层")
    finally:
        verification.close()


def _build_case_violations(
    case: OcrBenchmarkCase,
    adaptive_result: PdfOcrResult,
    adaptive_similarity: float,
    improvement: float,
) -> tuple[str, ...]:
    """按 manifest 的独立阈值构造单样本失败原因。"""
    violations: list[str] = []
    if adaptive_similarity < case.min_adaptive_similarity:
        violations.append(
            "adaptive similarity "
            f"{adaptive_similarity:.4f} < {case.min_adaptive_similarity:.4f}",
        )
    if improvement < case.min_improvement:
        violations.append(
            f"improvement {improvement:.4f} < {case.min_improvement:.4f}",
        )
    if (
        case.allowed_strategies
        and adaptive_result.strategy not in case.allowed_strategies
    ):
        violations.append(
            "strategy "
            f"{adaptive_result.strategy} not in {','.join(case.allowed_strategies)}",
        )
    if len(adaptive_result.candidate_summaries) < 2:
        violations.append("adaptive run did not compare multiple candidates")
    summaries_by_strategy = {
        summary.strategy: summary
        for summary in adaptive_result.candidate_summaries
    }
    for required_strategy in case.required_candidate_strategies:
        summary = summaries_by_strategy.get(required_strategy)
        if summary is None or summary.status != "succeeded":
            violations.append(
                f"required candidate {required_strategy} did not succeed",
            )
    return tuple(violations)


def evaluate_ocr_benchmark_case(
    case: OcrBenchmarkCase,
    baseline_result: PdfOcrResult,
    adaptive_result: PdfOcrResult,
    elapsed_seconds: float,
) -> OcrBenchmarkCaseResult:
    """计算单样本质量分、提升量和阈值结论。"""
    baseline_similarity = calculate_ocr_text_similarity(
        case.expected_text,
        baseline_result.text,
    )
    adaptive_similarity = calculate_ocr_text_similarity(
        case.expected_text,
        adaptive_result.text,
    )
    improvement = round(adaptive_similarity - baseline_similarity, 4)
    violations = _build_case_violations(
        case,
        adaptive_result,
        adaptive_similarity,
        improvement,
    )
    return OcrBenchmarkCaseResult(
        case_id=case.case_id,
        description=case.description,
        expected_text=case.expected_text,
        baseline_text=baseline_result.text,
        adaptive_text=adaptive_result.text,
        baseline_similarity=baseline_similarity,
        adaptive_similarity=adaptive_similarity,
        improvement=improvement,
        adaptive_confidence=adaptive_result.confidence,
        selected_strategy=adaptive_result.strategy,
        selected_psm=adaptive_result.psm,
        selected_rotation=adaptive_result.rotation,
        candidate_count=len(adaptive_result.candidate_summaries),
        elapsed_seconds=round(elapsed_seconds, 3),
        violations=violations,
    )


def get_tesseract_version() -> str:
    """读取本地 Tesseract 首行版本，不暴露路径或环境变量。"""
    try:
        completed = subprocess.run(
            ["tesseract", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
            text=True,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return "unavailable"
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    return first_line.strip() or "unknown"


def run_ocr_benchmark(
    manifest: OcrBenchmarkManifest,
    artifacts_directory: Path,
) -> OcrBenchmarkReport:
    """生成全部 PDF 并用生产基线/自适应 engine 执行真实评测。"""
    started_at = time.monotonic()
    case_results: list[OcrBenchmarkCaseResult] = []
    artifacts_directory.mkdir(parents=True, exist_ok=True)
    for case in manifest.cases:
        pdf_path = artifacts_directory / f"{case.case_id}.pdf"
        generate_ocr_benchmark_pdf(case, pdf_path)
        document = pymupdf.open(pdf_path)
        case_started_at = time.monotonic()
        try:
            page = document.load_page(0)
            baseline_result = run_pdf_page_ocr(page, adaptive=False)
            adaptive_result = run_pdf_page_ocr(page, adaptive=True)
        finally:
            document.close()
        case_results.append(evaluate_ocr_benchmark_case(
            case,
            baseline_result,
            adaptive_result,
            time.monotonic() - case_started_at,
        ))

    total_seconds = round(time.monotonic() - started_at, 3)
    average_similarity = round(
        sum(result.adaptive_similarity for result in case_results)
        / len(case_results),
        4,
    )
    aggregate_violations: list[str] = []
    if average_similarity < manifest.aggregate.min_average_adaptive_similarity:
        aggregate_violations.append(
            "average adaptive similarity "
            f"{average_similarity:.4f} < "
            f"{manifest.aggregate.min_average_adaptive_similarity:.4f}",
        )
    if total_seconds > manifest.aggregate.max_total_seconds:
        aggregate_violations.append(
            f"total seconds {total_seconds:.3f} > "
            f"{manifest.aggregate.max_total_seconds:.3f}",
        )
    return OcrBenchmarkReport(
        schema_version=OCR_BENCHMARK_SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        tesseract_version=get_tesseract_version(),
        average_adaptive_similarity=average_similarity,
        total_seconds=total_seconds,
        violations=tuple(aggregate_violations),
        cases=tuple(case_results),
    )


def serialize_ocr_benchmark_report(report: OcrBenchmarkReport) -> dict[str, Any]:
    """将 benchmark 报告转换为稳定 JSON 对象。"""
    payload = asdict(report)
    payload["passed"] = report.passed
    for case_payload, case in zip(payload["cases"], report.cases, strict=True):
        case_payload["passed"] = case.passed
    return payload


def render_ocr_benchmark_markdown(report: OcrBenchmarkReport) -> str:
    """生成适合 CI artifact 和人工复核的 Markdown 报告。"""
    status = "PASS" if report.passed else "FAIL"
    lines = [
        "# PDF OCR Regression Report",
        "",
        f"- Status: **{status}**",
        f"- Generated at: `{report.generated_at}`",
        f"- Tesseract: `{report.tesseract_version}`",
        f"- Average adaptive similarity: `{report.average_adaptive_similarity:.4f}`",
        f"- Total time: `{report.total_seconds:.3f}s`",
        "",
        "| Case | Baseline | Adaptive | Delta | Strategy | Candidates | Time | Status |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for case in report.cases:
        lines.append(
            f"| `{case.case_id}` | {case.baseline_similarity:.4f} | "
            f"{case.adaptive_similarity:.4f} | {case.improvement:+.4f} | "
            f"`{case.selected_strategy}` | {case.candidate_count} | "
            f"{case.elapsed_seconds:.3f}s | {'PASS' if case.passed else 'FAIL'} |",
        )
    failures = [
        f"{case.case_id}: {violation}"
        for case in report.cases
        for violation in case.violations
    ] + list(report.violations)
    if failures:
        lines.extend(["", "## Violations", ""])
        lines.extend(f"- {failure}" for failure in failures)
    return "\n".join(lines) + "\n"


def write_ocr_benchmark_reports(
    report: OcrBenchmarkReport,
    json_path: Path | None,
    markdown_path: Path | None,
) -> None:
    """按需写入 JSON 与 Markdown 报告。"""
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(
                serialize_ocr_benchmark_report(report),
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(
            render_ocr_benchmark_markdown(report),
            encoding="utf-8",
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析 OCR benchmark CLI 参数。"""
    parser = argparse.ArgumentParser(
        description="Generate synthetic scan PDFs and run the real OCR regression gate.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT_PATH)
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT_PATH,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """运行 benchmark，打印摘要并以稳定退出码表示门禁结果。"""
    args = parse_args(argv)
    try:
        manifest = load_ocr_benchmark_manifest(args.manifest)
        if args.artifacts_dir is not None:
            report = run_ocr_benchmark(manifest, args.artifacts_dir)
        else:
            with TemporaryDirectory(prefix="firstrag-ocr-eval-") as directory:
                report = run_ocr_benchmark(manifest, Path(directory))
        write_ocr_benchmark_reports(
            report,
            args.json_report,
            args.markdown_report,
        )
    except (OcrBenchmarkConfigError, OSError, ValueError) as exc:
        print(f"PDF OCR regression gate: ERROR\n- {exc}")
        return 2

    print(
        "PDF OCR regression gate: "
        f"{'PASS' if report.passed else 'FAIL'} "
        f"cases={len(report.cases)} "
        f"average={report.average_adaptive_similarity:.4f} "
        f"seconds={report.total_seconds:.3f}",
    )
    for case in report.cases:
        print(
            f"- {case.case_id}: "
            f"baseline={case.baseline_similarity:.4f} "
            f"adaptive={case.adaptive_similarity:.4f} "
            f"strategy={case.selected_strategy} "
            f"status={'PASS' if case.passed else 'FAIL'}",
        )
        for violation in case.violations:
            print(f"  - {violation}")
    for violation in report.violations:
        print(f"- {violation}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
