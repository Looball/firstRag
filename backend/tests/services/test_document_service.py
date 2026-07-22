"""文档发现与切分服务的单元测试。"""

from contextlib import redirect_stdout
from html import escape
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf

from app.services.documents.document_service import (
    ImageDocumentParseError,
    PdfOcrError,
    PdfOcrResult,
    build_vector_store,
    get_document_paths,
    load_document,
    parse_tesseract_tsv_confidence,
    run_pdf_page_ocr,
    split_documents,
)
from app.services.llm_service import ChatModelSettings
from app.services.user_settings_service import EffectiveChatModelConfig


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f"
    b"\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_pdf_fixture(path: Path, page_texts: list[str]) -> None:
    """创建包含指定逐页文本的真实 PDF 测试文件。"""
    document = pymupdf.open()
    try:
        for page_text in page_texts:
            page = document.new_page()
            page.insert_text((72, 72), page_text, fontsize=12)
        document.save(path)
    finally:
        document.close()


def create_mixed_pdf_fixture(path: Path) -> None:
    """创建一页原生文本和一页纯图片的混合 PDF。"""
    image_source = pymupdf.open()
    image_page = image_source.new_page()
    image_page.insert_text(
        (72, 120),
        "T072 SCANNED PAGE TARGET",
        fontsize=24,
    )
    image_bytes = image_page.get_pixmap(
        dpi=200,
        alpha=False,
    ).tobytes("png")

    document = pymupdf.open()
    try:
        native_page = document.new_page()
        native_page.insert_text(
            (72, 120),
            "T072 NATIVE PAGE TEXT",
            fontsize=18,
        )
        scanned_page = document.new_page()
        scanned_page.insert_image(scanned_page.rect, stream=image_bytes)
        document.save(path)
    finally:
        document.close()
        image_source.close()


def create_scanned_pdf_fixture(path: Path, page_texts: list[str]) -> None:
    """创建每页仅含文字栅格图、没有原生文本层的扫描 PDF。"""
    document = pymupdf.open()
    try:
        for page_text in page_texts:
            image_source = pymupdf.open()
            try:
                image_page = image_source.new_page()
                image_page.insert_text((72, 120), page_text, fontsize=24)
                image_bytes = image_page.get_pixmap(
                    dpi=200,
                    alpha=False,
                ).tobytes("png")
            finally:
                image_source.close()
            scanned_page = document.new_page()
            scanned_page.insert_image(scanned_page.rect, stream=image_bytes)
        document.save(path)
    finally:
        document.close()


def create_docx_fixture(
    path: Path,
    paragraphs: list[tuple[str, str | None]],
) -> None:
    """创建只含主文档 XML 的最小 DOCX 测试文件。"""
    paragraph_xml = []
    for text, style in paragraphs:
        style_xml = (
            f'<w:pPr><w:pStyle w:val="{escape(style)}"/></w:pPr>'
            if style
            else ""
        )
        text_xml = (
            f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
            if text
            else ""
        )
        paragraph_xml.append(f"<w:p>{style_xml}{text_xml}</w:p>")

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f'{"".join(paragraph_xml)}<w:sectPr/></w:body></w:document>'
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)


class FakeVisionModel:
    """测试用 vision 模型，记录调用消息并返回固定解析文本。"""

    def __init__(self) -> None:
        """初始化调用记录。"""
        self.messages = []

    def invoke(self, messages):
        """模拟 LangChain ChatModel invoke。"""
        self.messages = messages
        return Mock(content="# 图片解析\n\n唯一标识：FirstRAGImageEval-test")


class DocumentServiceTests(unittest.TestCase):
    """验证文档扫描结果的过滤和稳定性。"""

    def test_get_document_paths_returns_sorted_supported_files(self) -> None:
        """支持的文件应按路径排序，且忽略不支持的扩展名。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested_directory = root / "nested"
            nested_directory.mkdir()
            for relative_path in (
                "z-last.txt",
                "a-first.md",
                "nested/middle.PDF",
                "image.png",
                "ignored.gif",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            document_paths = get_document_paths(root)

        self.assertEqual(
            document_paths,
            sorted(
                [
                    root / "a-first.md",
                    root / "image.png",
                    root / "nested" / "middle.PDF",
                    root / "z-last.txt",
                ]
            ),
        )

    def test_build_vector_store_does_not_print_debug_output(self) -> None:
        """批量建库应使用 logger 记录进度，避免默认污染 stdout。"""
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "sample.md").write_text("# 标题\n\n正文内容", encoding="utf-8")
            persist_directory = root / "vector_db"

            mock_vector_store = Mock()
            mock_vector_store._collection.count.return_value = 1
            stdout = StringIO()

            with patch(
                "app.services.documents.document_service.create_embedding_model",
                return_value=Mock(),
            ) as mock_create_embedding_model, patch(
                "app.services.documents.document_service.Chroma.from_documents",
                return_value=mock_vector_store,
            ), redirect_stdout(stdout):
                result = build_vector_store(
                    folder_path=root,
                    persist_directory=persist_directory,
                    user_id=42,
                )

        self.assertIs(result, mock_vector_store)
        self.assertEqual(stdout.getvalue(), "")
        mock_create_embedding_model.assert_called_once_with(42)

    def test_pdf_chunks_keep_real_page_numbers_and_global_indexes(self) -> None:
        """PDF 分块应保留真实页码，并在跨页后继续递增 chunk index。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "three-pages.pdf"
            create_pdf_fixture(
                pdf_path,
                [
                    "T071 PDF PAGE ONE UNIQUE",
                    "T071 PDF PAGE TWO TARGET",
                    "T071 PDF PAGE THREE UNIQUE",
                ],
            )

            documents = load_document(
                pdf_path,
                file_id="pdf-file",
                user_id=7,
            )
            chunks = split_documents(documents)

        self.assertEqual(len(documents), 3)
        self.assertEqual(
            [document.metadata["page_number"] for document in documents],
            [1, 2, 3],
        )
        self.assertEqual(
            [document.metadata["page_index"] for document in documents],
            [0, 1, 2],
        )
        self.assertTrue(
            all(document.metadata["page_count"] == 3 for document in documents),
        )
        self.assertEqual(
            [chunk.metadata["chunk_index"] for chunk in chunks],
            list(range(len(chunks))),
        )
        target_chunk = next(
            chunk for chunk in chunks if "PAGE TWO TARGET" in chunk.page_content
        )
        self.assertEqual(target_chunk.metadata["page_number"], 2)

    def test_mixed_pdf_only_uses_ocr_for_scanned_page(self) -> None:
        """混合 PDF 只应 OCR 无文本层页面，并保留逐页解析方式。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "mixed.pdf"
            create_mixed_pdf_fixture(pdf_path)

            with patch(
                "app.services.documents.document_service.PDF_OCR_ENABLED",
                True,
            ), patch(
                "app.services.documents.document_service.PDF_OCR_MAX_PAGES",
                10,
            ), patch(
                "app.services.documents.document_service.run_pdf_page_ocr",
                return_value=PdfOcrResult(
                    text="T072 OCR RECOGNIZED TARGET",
                    confidence=88.25,
                    word_count=4,
                ),
            ) as run_ocr:
                documents = load_document(
                    pdf_path,
                    file_id="mixed-pdf",
                    user_id=7,
                )

        self.assertEqual(len(documents), 2)
        self.assertEqual(
            [document.metadata["pdf_parse_method"] for document in documents],
            ["native_text", "ocr"],
        )
        self.assertEqual(documents[1].metadata["ocr_engine"], "tesseract")
        self.assertEqual(documents[1].metadata["ocr_confidence"], 88.25)
        self.assertEqual(documents[1].metadata["ocr_quality"], "good")
        self.assertEqual(documents[1].metadata["ocr_attempt"], 1)
        self.assertEqual(documents[1].metadata["page_number"], 2)
        self.assertIn("OCR RECOGNIZED", documents[1].page_content)
        run_ocr.assert_called_once()

    def test_pdf_ocr_page_limit_is_enforced_before_recognition(self) -> None:
        """待 OCR 页数超过上限时应安全失败且不启动识别引擎。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "two-scanned-pages.pdf"
            create_scanned_pdf_fixture(
                pdf_path,
                ["T072 SCAN ONE", "T072 SCAN TWO"],
            )

            with patch(
                "app.services.documents.document_service.PDF_OCR_ENABLED",
                True,
            ), patch(
                "app.services.documents.document_service.PDF_OCR_MAX_PAGES",
                1,
            ), patch(
                "app.services.documents.document_service.run_pdf_page_ocr",
            ) as run_ocr:
                with self.assertRaises(PdfOcrError):
                    load_document(
                        pdf_path,
                        file_id="ocr-over-limit",
                        user_id=7,
                    )

        run_ocr.assert_not_called()

    def test_forced_pdf_page_ocr_records_second_attempt(self) -> None:
        """强制页应进入 OCR，并记录重新识别 attempt。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "native.pdf"
            create_pdf_fixture(pdf_path, ["T073 NATIVE PAGE"])

            with patch(
                "app.services.documents.document_service.run_pdf_page_ocr",
                return_value=PdfOcrResult(
                    text="T073 FORCED OCR PAGE",
                    confidence=52.5,
                    word_count=4,
                ),
            ):
                documents = load_document(
                    pdf_path,
                    file_id="forced-ocr",
                    user_id=7,
                    force_ocr_page_numbers={1},
                )

        self.assertEqual(documents[0].page_content, "T073 FORCED OCR PAGE")
        self.assertEqual(documents[0].metadata["ocr_attempt"], 2)
        self.assertEqual(documents[0].metadata["ocr_quality"], "low")
        self.assertEqual(documents[0].metadata["ocr_confidence"], 52.5)

    def test_pdf_ocr_attempt_continues_from_persisted_history(self) -> None:
        """后续 OCR 应从页面历史 attempt 单调递增。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "scanned.pdf"
            create_scanned_pdf_fixture(pdf_path, ["T078 OCR HISTORY"])

            with patch(
                "app.services.documents.document_service.run_pdf_page_ocr",
                return_value=PdfOcrResult(
                    text="T078 OCR HISTORY RUN FOUR",
                    confidence=76.25,
                    word_count=5,
                ),
            ):
                documents = load_document(
                    pdf_path,
                    file_id="ocr-history",
                    user_id=7,
                    previous_ocr_attempts={1: 3},
                )

        self.assertEqual(documents[0].metadata["ocr_attempt"], 4)
        self.assertEqual(
            documents[0].metadata["_ocr_history_text"],
            "T078 OCR HISTORY RUN FOUR",
        )

    def test_pdf_ocr_page_uses_manual_correction_and_keeps_confidence(self) -> None:
        """人工修订应覆盖正文，同时保留本次 OCR 质量与修订版本。"""
        with TemporaryDirectory() as temporary_directory:
            pdf_path = Path(temporary_directory) / "scanned.pdf"
            create_scanned_pdf_fixture(pdf_path, ["T074 ORIGINAL OCR"])

            with patch(
                "app.services.documents.document_service.run_pdf_page_ocr",
                return_value=PdfOcrResult(
                    text="T074 ORIGINAL OCR",
                    confidence=48.75,
                    word_count=3,
                ),
            ):
                documents = load_document(
                    pdf_path,
                    file_id="corrected-ocr",
                    user_id=7,
                    pdf_ocr_corrections={
                        1: {
                            "corrected_text": "T074 HUMAN CORRECTED TEXT",
                            "revision": 3,
                            "updated_at": "2026-07-21T12:00:00+08:00",
                        },
                    },
                )

        self.assertEqual(documents[0].page_content, "T074 HUMAN CORRECTED TEXT")
        self.assertEqual(documents[0].metadata["ocr_confidence"], 48.75)
        self.assertEqual(documents[0].metadata["ocr_quality"], "low")
        self.assertEqual(
            documents[0].metadata["ocr_text_source"],
            "manual_correction",
        )
        self.assertTrue(documents[0].metadata["ocr_correction_applied"])
        self.assertEqual(documents[0].metadata["ocr_correction_revision"], 3)

    def test_tesseract_confidence_is_weighted_by_word_characters(self) -> None:
        """较长 word 应在页面置信度中获得更高权重。"""
        confidence, word_count = parse_tesseract_tsv_confidence(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
            "left\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t50\tA\n"
            "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t90\tLONG\n"
            "4\t1\t1\t1\t1\t0\t0\t0\t10\t10\t-1\t\n",
        )

        self.assertEqual(confidence, 82.0)
        self.assertEqual(word_count, 2)

    def test_pdf_ocr_timeout_returns_safe_error(self) -> None:
        """Tesseract 单页超时应转换为稳定且不含内部路径的错误。"""
        page = Mock()
        page.get_pixmap.return_value.tobytes.return_value = b"png-bytes"
        with patch(
            "app.services.documents.document_service.subprocess.run",
            side_effect=subprocess.TimeoutExpired("tesseract", 60),
        ):
            with self.assertRaisesRegex(PdfOcrError, "单页识别超时"):
                run_pdf_page_ocr(page)

    def test_docx_chunks_keep_original_paragraph_ranges(self) -> None:
        """DOCX 分块应保留含空段落间隔的原始 OOXML 段落范围。"""
        with TemporaryDirectory() as temporary_directory:
            docx_path = Path(temporary_directory) / "paragraphs.docx"
            create_docx_fixture(
                docx_path,
                [
                    ("第一章", "Heading1"),
                    ("第一章正文", None),
                    ("", None),
                    ("第二章目标", "标题2"),
                    ("目标段落正文 T071-DOCX-TARGET", None),
                ],
            )

            documents = load_document(
                docx_path,
                file_id="docx-file",
                user_id=7,
            )
            chunks = split_documents(documents)

        self.assertEqual(
            [
                (
                    document.metadata["paragraph_start"],
                    document.metadata["paragraph_end"],
                )
                for document in documents
            ],
            [(1, 2), (4, 5)],
        )
        self.assertEqual(
            [chunk.metadata["chunk_index"] for chunk in chunks],
            list(range(len(chunks))),
        )
        target_chunk = next(
            chunk for chunk in chunks if "T071-DOCX-TARGET" in chunk.page_content
        )
        self.assertEqual(target_chunk.metadata["paragraph_start"], 4)
        self.assertEqual(target_chunk.metadata["paragraph_end"], 5)

    def test_load_image_document_uses_user_vision_model(self) -> None:
        """图片文件应通过当前用户 vision 模型解析为可检索 Markdown。"""
        with TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "chart.png"
            image_path.write_bytes(PNG_BYTES)
            fake_model = FakeVisionModel()

            with patch(
                "app.services.documents.document_service.get_effective_chat_model_config",
                return_value=EffectiveChatModelConfig(
                    settings=ChatModelSettings(
                        provider="qwen",
                        model="qwen-vl-plus",
                        api_key="sk-test",
                        base_url=None,
                        temperature=0.2,
                        max_tokens=1000,
                        timeout_seconds=60,
                        max_retries=2,
                    ),
                    credential_mode="user",
                ),
            ), patch(
                "app.services.documents.document_service.create_openai_compatible_chat_model",
                return_value=fake_model,
            ):
                documents = load_document(
                    image_path,
                    file_id="file-1",
                    user_id=1,
                    original_name="用户上传图表.png",
                )

        self.assertEqual(len(documents), 1)
        self.assertIn("FirstRAGImageEval-test", documents[0].page_content)
        self.assertIn("用户上传图表.png", documents[0].page_content)
        self.assertEqual(documents[0].metadata["file_name"], "用户上传图表.png")
        self.assertEqual(documents[0].metadata["file_type"], "image")
        self.assertEqual(documents[0].metadata["image_mime_type"], "image/png")
        self.assertEqual(documents[0].metadata["image_parse_method"], "vision_llm")
        self.assertEqual(documents[0].metadata["image_parse_provider"], "qwen")
        self.assertEqual(documents[0].metadata["image_parse_model"], "qwen-vl-plus")
        message_content = fake_model.messages[0].content
        self.assertEqual(message_content[0]["type"], "text")
        self.assertIn("用户上传图表.png", message_content[0]["text"])
        self.assertTrue(
            message_content[1]["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )

    def test_load_image_document_requires_vision_model(self) -> None:
        """当前聊天模型不支持 vision 时，图片解析应给出清晰错误。"""
        with TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "chart.png"
            image_path.write_bytes(PNG_BYTES)

            with patch(
                "app.services.documents.document_service.get_effective_chat_model_config",
                return_value=EffectiveChatModelConfig(
                    settings=ChatModelSettings(
                        provider="qwen",
                        model="qwen-plus",
                        api_key="sk-test",
                        base_url=None,
                        temperature=0.2,
                        max_tokens=1000,
                        timeout_seconds=60,
                        max_retries=2,
                    ),
                    credential_mode="user",
                ),
            ):
                with self.assertRaises(ImageDocumentParseError) as exc:
                    load_document(image_path, file_id="file-1", user_id=1)

        self.assertIn("支持视觉能力", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
