import base64
import csv
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from uuid import UUID
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage

# 将docx转为md文件
import mammoth
from markdownify import markdownify

import pymupdf
import pymupdf4llm

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.core.config import (
    PDF_OCR_DPI,
    PDF_OCR_ENABLED,
    PDF_OCR_LANGUAGES,
    PDF_OCR_LOW_CONFIDENCE_THRESHOLD,
    PDF_OCR_MAX_PAGES,
    PDF_OCR_MIN_NATIVE_TEXT_CHARACTERS,
    PDF_OCR_TIMEOUT_SECONDS,
    VECTOR_STORE_PATH,
)
from app.services.llm_service import (
    chat_model_supports_images,
    create_openai_compatible_chat_model,
)
from app.services.user_settings_service import get_effective_chat_model_config
from app.services.vectors.embedding_model import create_embedding_model


logger = logging.getLogger(__name__)

TEXT_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
IMAGE_DOCUMENT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_DOCUMENT_EXTENSIONS = TEXT_DOCUMENT_EXTENSIONS | IMAGE_DOCUMENT_EXTENSIONS
IMAGE_EXTENSION_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
TEXT_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
    "application/markdown",
    "text/x-markdown",
    "text/markdown",
    "text/plain",
}
SUPPORTED_DOCUMENT_MIME_TYPES = {
    *TEXT_DOCUMENT_MIME_TYPES,
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}
MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
    ("#####", "h5"),
    ("######", "h6"),
]
TEXT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
DOCX_BLOCK_MAX_CHARACTERS = 900
WORDPROCESSINGML_NAMESPACE = (
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
)
WORDPROCESSINGML_NAMESPACES = {"w": WORDPROCESSINGML_NAMESPACE}
WORD_PARAGRAPH_TAG = f"{{{WORDPROCESSINGML_NAMESPACE}}}p"
WORD_TEXT_TAG = f"{{{WORDPROCESSINGML_NAMESPACE}}}t"
WORD_TAB_TAG = f"{{{WORDPROCESSINGML_NAMESPACE}}}tab"
WORD_BREAK_TAG = f"{{{WORDPROCESSINGML_NAMESPACE}}}br"
WORD_VALUE_ATTRIBUTE = f"{{{WORDPROCESSINGML_NAMESPACE}}}val"
PDF_OCR_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_+./-]+$")


class UnsupportedDocumentTypeError(ValueError):
    """文件类型不在知识库解析支持范围内时抛出。"""


class EmptyDocumentError(ValueError):
    """文件可读取但没有解析出可入库文本时抛出。"""


class ImageDocumentParseError(ValueError):
    """图片文件无法通过 vision 模型解析时抛出。"""


class PdfOcrError(ValueError):
    """扫描 PDF 的本地 OCR 无法安全完成时抛出。"""


@dataclass(frozen=True)
class PdfOcrResult:
    """单页 Tesseract 文本、置信度和有效 word 数量。"""

    text: str
    confidence: float | None
    word_count: int


def get_supported_document_type_text() -> str:
    """返回面向用户展示的支持文件类型说明。"""
    return "PDF、DOCX、Markdown、TXT、PNG、JPEG 或 WebP"


def normalize_image_mime_type(mime_type: str | None) -> str:
    """标准化知识库图片 MIME type。"""
    normalized = (mime_type or "").split(";", maxsplit=1)[0].strip().lower()
    return "image/jpeg" if normalized == "image/jpg" else normalized


def is_image_document_file_name(file_name: str) -> bool:
    """判断文件名是否属于知识库图片类型。"""
    return Path(file_name).suffix.lower() in IMAGE_DOCUMENT_EXTENSIONS


def is_supported_image_mime_type(mime_type: str | None) -> bool:
    """判断 MIME type 是否可作为图片知识文件。"""
    normalized = normalize_image_mime_type(mime_type)
    allowed_mime_types = {
        "",
        "application/octet-stream",
        *IMAGE_EXTENSION_MIME_TYPES.values(),
    }
    return normalized in allowed_mime_types


def sniff_image_mime_type(content: bytes) -> str:
    """根据文件头识别知识库图片 MIME type。"""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise UnsupportedDocumentTypeError("无法识别图片格式，仅支持 PNG、JPEG 或 WebP")


def validate_supported_image_content(
    file_name: str,
    content_sample: bytes,
    mime_type: str | None = None,
) -> str:
    """校验图片内容、扩展名和声明 MIME 是否一致。"""
    suffix = Path(file_name).suffix.lower()
    expected_mime_type = IMAGE_EXTENSION_MIME_TYPES.get(suffix)
    if expected_mime_type is None:
        raise UnsupportedDocumentTypeError(
            build_unsupported_document_type_message(file_name),
        )

    sniffed_mime_type = sniff_image_mime_type(content_sample)
    if sniffed_mime_type != expected_mime_type:
        raise UnsupportedDocumentTypeError("图片内容与文件扩展名不一致")

    normalized_mime_type = normalize_image_mime_type(mime_type)
    if (
        normalized_mime_type
        and normalized_mime_type != "application/octet-stream"
        and normalized_mime_type != sniffed_mime_type
    ):
        raise UnsupportedDocumentTypeError("图片内容与声明的 MIME 类型不一致")

    return sniffed_mime_type


def is_supported_document_file(
    file_name: str,
    mime_type: str | None = None,
) -> bool:
    """判断上传文件是否属于当前解析链路支持的类型。"""
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return False

    if not mime_type:
        return True

    normalized_mime_type = mime_type.split(";", maxsplit=1)[0].strip().lower()
    if suffix in IMAGE_DOCUMENT_EXTENSIONS:
        return is_supported_image_mime_type(normalized_mime_type)

    return (
        not normalized_mime_type
        or normalized_mime_type in TEXT_DOCUMENT_MIME_TYPES
    )


def build_unsupported_document_type_message(file_name: str) -> str:
    """生成不支持文件类型的安全错误信息。"""
    suffix = Path(file_name).suffix.lower() or "无扩展名"
    return (
        f"不支持的文件类型：{suffix}。"
        f"请上传 {get_supported_document_type_text()} 文件。"
    )


def get_document_paths(folder_path: str | Path = "./local_doc") -> list[Path]:
    """获取本地知识库中当前支持的文档路径。"""
    document_paths = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS:
                document_paths.append(file_path)

    # 文件系统遍历顺序不保证稳定；固定排序可避免批量建库时文件 ID 随运行变化。
    return sorted(document_paths)


def convert_docx2md(docx_path) -> str:
    """将 DOCX 转换为 Markdown，并忽略内嵌图片。"""

    with open(docx_path, "rb") as file:
        result = mammoth.convert_to_html(
            file,
            convert_image=lambda image: [],
        )

    return markdownify(result.value, heading_style="ATX")


def get_docx_heading_level(paragraph: ElementTree.Element) -> int | None:
    """从 OOXML paragraph style 读取 1-6 级标题。"""
    style = paragraph.find("./w:pPr/w:pStyle", WORDPROCESSINGML_NAMESPACES)
    if style is None:
        return None

    style_name = str(style.get(WORD_VALUE_ATTRIBUTE) or "").strip()
    match = re.search(r"(?:heading|标题)\s*([1-6])", style_name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def get_docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    """按 OOXML 节点顺序提取单个 paragraph 的文本、制表符和换行。"""
    parts: list[str] = []
    for element in paragraph.iter():
        if element.tag == WORD_TEXT_TAG and element.text:
            parts.append(element.text)
        elif element.tag == WORD_TAB_TAG:
            parts.append("\t")
        elif element.tag == WORD_BREAK_TAG:
            parts.append("\n")
    return "".join(parts).strip()


def extract_docx_paragraphs(file_path: Path) -> list[dict[str, object]]:
    """从 DOCX 主文档 XML 提取保留原始序号的非空段落。"""
    try:
        with ZipFile(file_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError, OSError) as exc:
        raise EmptyDocumentError("DOCX 文件结构无效或缺少正文") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise EmptyDocumentError("DOCX 正文 XML 无法解析") from exc

    paragraphs = []
    for paragraph_number, paragraph in enumerate(
        root.iter(WORD_PARAGRAPH_TAG),
        start=1,
    ):
        text = get_docx_paragraph_text(paragraph)
        if not text:
            continue
        paragraphs.append({
            "paragraph_number": paragraph_number,
            "text": text,
            "heading_level": get_docx_heading_level(paragraph),
        })
    return paragraphs


def build_docx_block_documents(
    file_path: Path,
    base_metadata: dict[str, str],
) -> list[Document]:
    """按标题和字符上限将 DOCX 段落组合为带位置范围的 Documents。"""
    paragraphs = extract_docx_paragraphs(file_path)
    if not paragraphs:
        raise EmptyDocumentError("DOCX 文件没有可索引正文")

    documents: list[Document] = []
    block_parts: list[str] = []
    block_start = 0
    block_end = 0

    def flush_block() -> None:
        """把当前段落块写成一个带准确范围的 Document。"""
        nonlocal block_parts, block_start, block_end
        if not block_parts:
            return
        documents.append(
            Document(
                page_content="\n\n".join(block_parts),
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                    "location_type": "docx_paragraphs",
                    "paragraph_start": block_start,
                    "paragraph_end": block_end,
                },
            )
        )
        block_parts = []
        block_start = 0
        block_end = 0

    for paragraph in paragraphs:
        paragraph_number = int(paragraph["paragraph_number"])
        paragraph_text = str(paragraph["text"])
        heading_level = paragraph.get("heading_level")
        formatted_text = (
            f"{'#' * int(heading_level)} {paragraph_text}"
            if isinstance(heading_level, int)
            else paragraph_text
        )
        candidate_length = sum(len(part) for part in block_parts)
        candidate_length += len(formatted_text) + (2 if block_parts else 0)
        if block_parts and (
            isinstance(heading_level, int)
            or candidate_length > DOCX_BLOCK_MAX_CHARACTERS
        ):
            flush_block()

        if not block_parts:
            block_start = paragraph_number
        block_parts.append(formatted_text)
        block_end = paragraph_number

    flush_block()
    return documents


def build_pdf_page_documents(
    file_path: Path,
    base_metadata: dict[str, str],
    force_ocr_page_numbers: set[int] | None = None,
) -> list[Document]:
    """逐页解析 PDF，并把真实 1-based 页码写入 Document metadata。"""
    page_chunks = pymupdf4llm.to_markdown(
        str(file_path),
        page_chunks=True,
        use_ocr=False,
    )
    if not isinstance(page_chunks, list):
        raise EmptyDocumentError("PDF 解析器没有返回逐页结果")

    minimum_native_characters = max(0, PDF_OCR_MIN_NATIVE_TEXT_CHARACTERS)
    ocr_page_indexes = {
        page_index
        for page_index, page_chunk in enumerate(page_chunks)
        if isinstance(page_chunk, dict)
        and count_effective_text_characters(
            str(page_chunk.get("text") or ""),
        ) < minimum_native_characters
    }
    normalized_force_pages = {
        int(page_number)
        for page_number in (force_ocr_page_numbers or set())
    }
    invalid_force_pages = {
        page_number
        for page_number in normalized_force_pages
        if page_number < 1 or page_number > len(page_chunks)
    }
    if invalid_force_pages:
        raise PdfOcrError("PDF OCR 强制重新识别页码超出范围")
    forced_page_indexes = {
        page_number - 1
        for page_number in normalized_force_pages
    }
    ocr_page_indexes.update(forced_page_indexes)
    if PDF_OCR_ENABLED and PDF_OCR_MAX_PAGES > 0:
        if len(ocr_page_indexes) > PDF_OCR_MAX_PAGES:
            raise PdfOcrError(
                "PDF OCR 页数超过配置上限，"
                f"最多允许 {PDF_OCR_MAX_PAGES} 页",
            )

    ocr_result_by_page: dict[int, PdfOcrResult] = {}
    if PDF_OCR_ENABLED and ocr_page_indexes:
        validate_pdf_ocr_runtime_config()
        try:
            pdf_document = pymupdf.open(str(file_path))
        except (OSError, RuntimeError, ValueError) as exc:
            raise PdfOcrError("PDF OCR 无法打开原始文档") from exc
        try:
            for page_index in sorted(ocr_page_indexes):
                if page_index >= pdf_document.page_count:
                    raise PdfOcrError("PDF OCR 页码与解析结果不一致")
                ocr_result_by_page[page_index] = run_pdf_page_ocr(
                    pdf_document.load_page(page_index),
                )
        finally:
            pdf_document.close()

    documents = []
    page_count = len(page_chunks)
    for page_index, page_chunk in enumerate(page_chunks):
        if not isinstance(page_chunk, dict):
            continue
        native_markdown_text = str(page_chunk.get("text") or "").strip()
        ocr_result = ocr_result_by_page.get(page_index)
        ocr_text = ocr_result.text.strip() if ocr_result is not None else ""
        markdown_text = ocr_text or native_markdown_text
        if not markdown_text:
            continue
        parse_method = "ocr" if ocr_text else "native_text"
        if parse_method == "ocr" and ocr_result is not None:
            confidence = ocr_result.confidence
            low_confidence_threshold = normalize_pdf_ocr_confidence_threshold(
                PDF_OCR_LOW_CONFIDENCE_THRESHOLD,
            )
            ocr_metadata = {
                "ocr_engine": "tesseract",
                "ocr_languages": PDF_OCR_LANGUAGES,
                "ocr_dpi": normalize_pdf_ocr_dpi(PDF_OCR_DPI),
                "ocr_quality": (
                    "unknown"
                    if confidence is None
                    else "low"
                    if confidence < low_confidence_threshold
                    else "good"
                ),
                "ocr_word_count": ocr_result.word_count,
                "ocr_attempt": 2 if page_index in forced_page_indexes else 1,
            }
            if confidence is not None:
                ocr_metadata["ocr_confidence"] = confidence
        else:
            ocr_metadata = {}
        documents.append(
            Document(
                page_content=markdown_text,
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                    "location_type": "pdf_page",
                    "page_index": page_index,
                    "page_number": page_index + 1,
                    "page_count": page_count,
                    "pdf_parse_method": parse_method,
                    **ocr_metadata,
                },
            )
        )

    if not documents:
        raise EmptyDocumentError("PDF 文件没有可索引正文")
    return documents


def count_effective_text_characters(text: str) -> int:
    """统计可表达正文的字母、数字或 CJK 字符，忽略 Markdown 标记。"""
    return sum(character.isalnum() for character in text)


def normalize_pdf_ocr_dpi(value: int) -> int:
    """将 OCR DPI 限制到兼顾识别质量和内存占用的安全范围。"""
    return min(600, max(72, value))


def normalize_pdf_ocr_confidence_threshold(value: int) -> int:
    """将低置信度阈值限制在 Tesseract 的 0-100 分数范围。"""
    return min(100, max(0, value))


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


def validate_pdf_ocr_runtime_config() -> None:
    """校验不会传入 shell 的 Tesseract 语言与资源限制配置。"""
    if not PDF_OCR_LANGUAGE_PATTERN.fullmatch(PDF_OCR_LANGUAGES):
        raise PdfOcrError("PDF OCR 语言配置无效")
    if PDF_OCR_TIMEOUT_SECONDS <= 0:
        raise PdfOcrError("PDF OCR 单页超时必须大于 0 秒")


def run_pdf_page_ocr(page: pymupdf.Page) -> PdfOcrResult:
    """单次调用 Tesseract，同时读取页面文本和 TSV confidence。"""
    dpi = normalize_pdf_ocr_dpi(PDF_OCR_DPI)
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    with TemporaryDirectory(prefix="firstrag-ocr-") as temporary_directory:
        output_base = Path(temporary_directory) / "page"
        command = [
            "tesseract",
            "stdin",
            str(output_base),
            "-l",
            PDF_OCR_LANGUAGES,
            "--dpi",
            str(dpi),
            "--psm",
            "3",
            "txt",
            "tsv",
        ]
        try:
            result = subprocess.run(
                command,
                input=pixmap.tobytes("png"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=PDF_OCR_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise PdfOcrError("PDF OCR 引擎不可用，请安装 Tesseract") from exc
        except subprocess.TimeoutExpired as exc:
            raise PdfOcrError("PDF OCR 单页识别超时") from exc
        except OSError as exc:
            raise PdfOcrError("PDF OCR 无法启动本地识别引擎") from exc

        if result.returncode != 0:
            raise PdfOcrError("PDF OCR 识别失败，请检查语言包和文件清晰度")
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
    )


def extract_chat_message_text(content: object) -> str:
    """从 LangChain/OpenAI-compatible 消息内容中提取文本。"""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return str(content or "").strip()


def build_image_parse_prompt(file_name: str) -> str:
    """构造图片入库解析提示词。"""
    return (
        "请读取这张图片，为知识库检索生成可搜索的中文 Markdown 文本。"
        "要求：\n"
        "1. 提取图片中所有清晰可见的文字，尽量保持原文。\n"
        "2. 如果是截图、表格、图表、票据或界面，请概括标题、字段、数值、"
        "对象关系和关键视觉信息。\n"
        "3. 如果某些文字无法辨认，请写“无法辨认”，不要编造。\n"
        "4. 输出只包含适合检索入库的内容，不要解释你的处理过程。\n\n"
        f"文件名：{file_name}"
    )


def ensure_image_document_vision_settings(user_id: int) -> None:
    """确认当前用户聊天模型可用于图片入库解析。"""
    try:
        model_config = get_effective_chat_model_config(user_id)
    except ValueError as exc:
        raise ImageDocumentParseError(
            "图片解析模型配置无效：请先在设置页配置支持 vision 的聊天模型。"
        ) from exc

    if not chat_model_supports_images(
        model_config.settings.provider,
        model_config.settings.model,
    ):
        raise ImageDocumentParseError(
            "图片解析需要支持视觉能力的聊天模型，请切换到 Qwen-VL、GLM-4V "
            "或其他 vision 模型后重新向量化。"
        )


def parse_image_document(
    file_path: Path,
    *,
    user_id: int,
    file_name: str,
) -> tuple[str, str, str, str]:
    """使用当前用户的 vision 聊天模型解析图片为可检索文本。"""
    image_bytes = file_path.read_bytes()
    image_mime_type = validate_supported_image_content(
        file_name,
        image_bytes,
    )
    try:
        model_config = get_effective_chat_model_config(user_id)
    except ValueError as exc:
        raise ImageDocumentParseError(
            "图片解析模型配置无效：请先在设置页配置支持 vision 的聊天模型。"
        ) from exc

    if not chat_model_supports_images(
        model_config.settings.provider,
        model_config.settings.model,
    ):
        raise ImageDocumentParseError(
            "图片解析需要支持视觉能力的聊天模型，请切换到 Qwen-VL、GLM-4V "
            "或其他 vision 模型后重新向量化。"
        )

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    model = create_openai_compatible_chat_model(model_config.settings)
    response = model.invoke([
        HumanMessage(
            content=[
                {"type": "text", "text": build_image_parse_prompt(file_name)},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime_type};base64,{encoded_image}",
                    },
                },
            ]
        )
    ])
    parsed_text = extract_chat_message_text(getattr(response, "content", response))
    if not parsed_text:
        raise EmptyDocumentError("图片没有解析出可入库文本")

    return (
        f"# 图片文件：{file_name}\n\n{parsed_text}",
        image_mime_type,
        model_config.settings.provider,
        model_config.settings.model,
    )


def load_document(
    file_path: Path,
    file_id: UUID | str,
    user_id: int | str | None = None,
    original_name: str | None = None,
    force_ocr_page_numbers: set[int] | None = None,
) -> list[Document]:
    """根据文件类型加载单个本地文档。"""
    display_name = original_name or file_path.name
    suffix = Path(display_name).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise UnsupportedDocumentTypeError(
            build_unsupported_document_type_message(display_name),
        )

    base_metadata = {
        "source": str(file_path),
        "file_name": display_name,
        "file_id": str(file_id),
        "file_type": suffix.removeprefix("."),
    }
    if user_id is not None:
        base_metadata["user_id"] = str(user_id)

    if suffix in IMAGE_DOCUMENT_EXTENSIONS:
        if user_id is None:
            raise ImageDocumentParseError(
                "图片解析需要当前用户上下文，请通过向量化任务处理图片文件。"
            )
        parsed_text, image_mime_type, provider, model = parse_image_document(
            file_path,
            user_id=int(user_id),
            file_name=display_name,
        )
        return [
            Document(
                page_content=parsed_text,
                metadata={
                    **base_metadata,
                    "file_type": "image",
                    "content_format": "markdown",
                    "image_mime_type": image_mime_type,
                    "image_parse_method": "vision_llm",
                    "image_parse_provider": provider,
                    "image_parse_model": model,
                },
            )
        ]

    if suffix == ".pdf":
        return build_pdf_page_documents(
            file_path,
            base_metadata,
            force_ocr_page_numbers=force_ocr_page_numbers,
        )

    if suffix == ".docx":
        return build_docx_block_documents(file_path, base_metadata)

    if suffix == ".md":
        return [
            Document(
                page_content=file_path.read_text(encoding="utf-8"),
                metadata={
                    **base_metadata,
                    "content_format": "markdown",
                },
            )
        ]

    if suffix == ".txt":
        return [
            Document(
                page_content=file_path.read_text(encoding="utf-8"),
                metadata={
                    **base_metadata,
                    "content_format": "plain_text",
                },
            )
        ]

    raise UnsupportedDocumentTypeError(
        build_unsupported_document_type_message(display_name),
    )


def split_document(document: Document) -> list[Document]:
    """按照文档内容格式切分单个文档。"""
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    markdown_chunk_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=TEXT_SEPARATORS,
    )
    plain_text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=TEXT_SEPARATORS,
    )

    if document.metadata.get("content_format") == "markdown":
        sections = markdown_splitter.split_text(document.page_content)
        for section in sections:
            # 标题切分器生成标题元数据，这里补回原始文件信息。
            section.metadata = {
                **document.metadata,
                **section.metadata,
            }
        return markdown_chunk_splitter.split_documents(sections)

    return plain_text_splitter.split_documents([document])


def split_documents(documents: list[Document]) -> list[Document]:
    """批量切分文档，并按用户和文件生成全局连续分块序号。"""
    chunks: list[Document] = []
    next_chunk_index_by_file: dict[tuple[str, str], int] = {}
    for document in documents:
        document_chunks = split_document(document)
        metadata = document.metadata
        sequence_key = (
            str(metadata.get("user_id") or ""),
            str(metadata.get("file_id") or metadata.get("source") or ""),
        )
        next_chunk_index = next_chunk_index_by_file.get(sequence_key, 0)
        for chunk in document_chunks:
            chunk_index = next_chunk_index
            chunk.metadata["chunk_index"] = chunk_index
            next_chunk_index += 1
        next_chunk_index_by_file[sequence_key] = next_chunk_index
        chunks.extend(document_chunks)

    return chunks


def build_vector_store(
    folder_path: str | Path = "./local_doc",
    persist_directory: str | Path = VECTOR_STORE_PATH,
    user_id: int | None = None,
) -> Chroma:
    """加载、切分本地文档并写入Chroma向量数据库。"""
    if user_id is None:
        raise ValueError("构建向量库需要传入已配置向量模型的 user_id")

    file_paths = get_document_paths(folder_path)
    logger.info("发现可入库文档数量：%s", len(file_paths))
    logger.debug("文档发现样例：%s", [str(path) for path in file_paths[:3]])

    documents = []
    for index, file_path in enumerate(file_paths):
        documents.extend(
            load_document(file_path, file_id=str(index), user_id=user_id)
        )

    split_docs = split_documents(documents)
    character_count = sum(len(doc.page_content) for doc in split_docs)

    logger.info(
        "文档切分完成：chunks=%s characters=%s",
        len(split_docs),
        character_count,
    )
    logger.debug("文档切分样例：%s", split_docs[:3])

    vectordb = Chroma.from_documents(
        documents=split_docs,
        embedding=create_embedding_model(user_id),
        persist_directory=str(persist_directory),
    )
    logger.info("向量库中存储的数量：%s", vectordb._collection.count())
    return vectordb


if __name__ == '__main__':
    docs = load_document(
        Path('../../../demo/local_doc/预训练模型微调.pdf'),
        file_id='123125',
    )
    print(docs)
    chunks = split_documents(docs)
    print(chunks)
    for chunk in chunks:
        print('*'*40)
        print(chunk.page_content)
