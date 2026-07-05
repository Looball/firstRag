"""文档发现与切分服务的单元测试。"""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from app.services.documents.document_service import (
    ImageDocumentParseError,
    build_vector_store,
    get_document_paths,
    load_document,
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
