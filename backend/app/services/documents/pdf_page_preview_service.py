"""PDF 目标页安全渲染服务。"""

from pathlib import Path

import pymupdf


PDF_PREVIEW_MAX_DIMENSION = 1800


class PdfPagePreviewValidationError(ValueError):
    """文件类型或页码不支持预览时抛出。"""


class PdfPagePreviewRenderError(RuntimeError):
    """PDF 无法打开或目标页无法渲染时抛出。"""


def render_pdf_page_preview(
    file_path: Path,
    page_number: int,
) -> bytes:
    """将 1-based PDF 目标页渲染为受限尺寸的 RGB PNG。"""
    if file_path.suffix.lower() != ".pdf":
        raise PdfPagePreviewValidationError("只有 PDF 文件支持页级预览")
    if page_number < 1:
        raise PdfPagePreviewValidationError("PDF 页码必须从 1 开始")

    try:
        document = pymupdf.open(str(file_path))
    except (OSError, RuntimeError, ValueError) as exc:
        raise PdfPagePreviewRenderError("PDF 文件无法打开") from exc

    try:
        if page_number > document.page_count:
            raise PdfPagePreviewValidationError("PDF 页面不存在")
        page = document.load_page(page_number - 1)
        longest_edge = max(float(page.rect.width), float(page.rect.height), 1.0)
        # 超大页面也必须向下采样，避免由不可信 PDF 页面尺寸放大内存占用。
        scale = min(2.0, PDF_PREVIEW_MAX_DIMENSION / longest_edge)
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
        return pixmap.tobytes("png")
    except PdfPagePreviewValidationError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise PdfPagePreviewRenderError("PDF 页面渲染失败") from exc
    finally:
        document.close()
