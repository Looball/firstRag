#!/usr/bin/env python3
"""从仓库自编 ground truth 生成确定性的教程 OCR PNG。"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_PATH = (
    REPOSITORY_ROOT / "docs/tutorials/fixtures/ocr_ground_truth.txt"
)
DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "tmp/tutorial-fixtures/firstrag-synthetic-ocr-card.png"
)


def load_ground_truth(path: Path) -> tuple[str, ...]:
    """读取受控 ground truth，并拒绝空白或异常大的输入。"""
    try:
        lines = tuple(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except OSError as exc:
        raise ValueError(f"无法读取 OCR ground truth：{path}") from exc
    if not 1 <= len(lines) <= 8:
        raise ValueError("OCR ground truth 必须包含 1 到 8 行非空文本")
    if any(len(line) > 80 for line in lines):
        raise ValueError("OCR ground truth 单行不能超过 80 个字符")
    return lines


def _load_font(size: int) -> ImageFont.ImageFont:
    """加载 Pillow 内置字体，避免依赖本机字体文件。"""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_ocr_card(lines: tuple[str, ...], output_path: Path) -> Path:
    """渲染带固定轻微旋转和模糊的合成 OCR 练习卡。"""
    canvas = Image.new("L", (1600, 900), color=245)
    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(72)
    body_font = _load_font(54)
    y_position = 110
    for index, line in enumerate(lines):
        font = title_font if index == 0 else body_font
        draw.text((130, y_position), line, fill=24, font=font)
        y_position += 150 if index == 0 else 125

    degraded = canvas.rotate(
        1.5,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor=255,
    ).filter(ImageFilter.GaussianBlur(radius=0.35))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    degraded.save(output_path, format="PNG", optimize=False)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""
    parser = argparse.ArgumentParser(
        description="生成不含第三方内容的 FirstRAG 教程 OCR PNG。"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_PATH,
        help="UTF-8 ground truth 文本路径。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="PNG 输出路径，默认写入已忽略的 tmp/。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """生成教程 OCR fixture 并打印不含敏感信息的输出位置。"""
    args = build_parser().parse_args(argv)
    lines = load_ground_truth(args.source)
    output_path = render_ocr_card(lines, args.output)
    print(f"Tutorial OCR fixture generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
