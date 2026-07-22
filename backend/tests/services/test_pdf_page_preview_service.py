"""PDF 目标页渲染服务测试。"""

import tempfile
import unittest
from pathlib import Path

import pymupdf

from app.services.documents.pdf_page_preview_service import (
    PDF_PREVIEW_MAX_DIMENSION,
    PdfPagePreviewValidationError,
    render_pdf_page_preview,
)


class PdfPagePreviewServiceTests(unittest.TestCase):
    """验证 PDF 页级 PNG 输出和页码边界。"""

    def test_render_pdf_page_preview_returns_png(self) -> None:
        """有效页面应渲染为 PNG，且不依赖浏览器 PDF 插件。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "preview.pdf"
            document = pymupdf.open()
            page = document.new_page(width=300, height=400)
            page.insert_text((40, 60), "T-075 PDF preview")
            document.save(str(pdf_path))
            document.close()

            rendered = render_pdf_page_preview(pdf_path, 1)

        self.assertTrue(rendered.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(rendered), 100)

    def test_render_pdf_page_preview_downsamples_oversized_page(self) -> None:
        """超大页面最长边也不得超过预览尺寸上限。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "oversized.pdf"
            document = pymupdf.open()
            document.new_page(width=3600, height=7200)
            document.save(str(pdf_path))
            document.close()

            rendered = render_pdf_page_preview(pdf_path, 1)
            pixmap = pymupdf.Pixmap(rendered)

        self.assertLessEqual(
            max(pixmap.width, pixmap.height),
            PDF_PREVIEW_MAX_DIMENSION,
        )

    def test_render_pdf_page_preview_rejects_out_of_range_page(self) -> None:
        """超过 PDF page_count 的页码应返回可理解的校验错误。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "preview.pdf"
            document = pymupdf.open()
            document.new_page()
            document.save(str(pdf_path))
            document.close()

            with self.assertRaisesRegex(
                PdfPagePreviewValidationError,
                "PDF 页面不存在",
            ):
                render_pdf_page_preview(pdf_path, 2)


if __name__ == "__main__":
    unittest.main()
