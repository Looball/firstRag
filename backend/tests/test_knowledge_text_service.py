"""Milvus parent/child 文本读取服务回归测试。"""

import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from app.services.vectors.knowledge_text_service import (
    get_file_chunk_context,
    list_file_text_rows,
    list_pdf_ocr_page_rows,
)
from app.services.vectors.vector_store import VectorRecord


class KnowledgeTextServiceTests(unittest.TestCase):
    """验证正文只通过 user-scoped Milvus boundary 读取。"""

    def _records(self) -> list[VectorRecord]:
        """构造跨 parent 和页面的有序 child records。"""
        return [
            VectorRecord(
                id=f"child-{index}",
                document=Document(
                    page_content=f"child {index}",
                    metadata={
                        "user_id": 7,
                        "file_id": "file-a",
                        "index_version": 3,
                        "chunk_index": index,
                        "parent_id": "parent-a" if index < 2 else "parent-b",
                        "parent_index": 0 if index < 2 else 1,
                        "child_index": index if index < 2 else 0,
                        "parent_content": (
                            "parent A" if index < 2 else "parent B"
                        ),
                        "page_number": index + 1,
                        "pdf_parse_method": "ocr" if index != 1 else "native_text",
                    },
                ),
            )
            for index in range(3)
        ]

    def test_list_file_rows_uses_scoped_vector_boundary(self) -> None:
        """读取必须把 user/file scope 传给 Milvus adapter。"""
        store = Mock()
        store.list_file_vectors.return_value = self._records()
        with patch(
            "app.services.vectors.knowledge_text_service.get_vector_store",
            return_value=store,
        ):
            rows = list_file_text_rows(user_id=7, file_id="file-a")

        store.list_file_vectors.assert_called_once_with(
            user_id=7,
            file_id="file-a",
        )
        self.assertEqual([row["content"] for row in rows], [
            "child 0",
            "child 1",
            "child 2",
        ])
        self.assertEqual(rows[0]["parent_content"], "parent A")

    def test_context_does_not_cross_parent_boundary(self) -> None:
        """相邻预览不能跨越目标 child 所属 parent。"""
        with patch(
            "app.services.vectors.knowledge_text_service.list_file_text_rows",
            return_value=[
                {
                    "chunk_index": index,
                    "index_version": 3,
                    "parent_id": "parent-a" if index < 2 else "parent-b",
                    "metadata": {},
                }
                for index in range(3)
            ],
        ):
            rows = get_file_chunk_context(
                user_id=7,
                file_id="file-a",
                chunk_index=1,
                radius=2,
                index_version=3,
            )

        self.assertEqual([row["chunk_index"] for row in rows], [0, 1])

    def test_ocr_page_list_uses_milvus_metadata(self) -> None:
        """OCR 清单应过滤 native page 并按页码返回代表 child。"""
        with patch(
            "app.services.vectors.knowledge_text_service.list_file_text_rows",
            return_value=[
                {
                    "metadata": record.document.metadata,
                    "chunk_index": index,
                }
                for index, record in enumerate(self._records())
            ],
        ):
            rows = list_pdf_ocr_page_rows(
                user_id=7,
                file_id="file-a",
                index_version=3,
            )

        self.assertEqual(
            [row["metadata"]["page_number"] for row in rows],
            [1, 3],
        )


if __name__ == "__main__":
    unittest.main()
