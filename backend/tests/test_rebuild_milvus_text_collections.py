"""Milvus 文本切换审计工具测试。"""

import unittest

from langchain_core.documents import Document

from app.services.vectors.vector_store import VectorRecord
from scripts.rebuild_milvus_text_collections import (
    CutoverError,
    audit_records,
    build_content_digest,
)


def build_record(
    *,
    child_id: str = "9:file-a:v3:p0:c0",
    child_content: str = "child text",
    parent_content: str = "parent text",
    index_version: int = 3,
) -> VectorRecord:
    """构造一条符合 v3 契约的 Milvus record。"""
    return VectorRecord(
        id=child_id,
        document=Document(
            page_content=child_content,
            metadata={
                "user_id": 9,
                "file_id": "file-a",
                "index_version": index_version,
                "parent_id": "9:file-a:v3:p0",
                "parent_content": parent_content,
            },
        ),
    )


class RebuildMilvusTextCollectionsTests(unittest.TestCase):
    """验证 cutover 工具只为完整 v3 数据放行。"""

    def test_audit_accepts_complete_child_and_parent_text(self) -> None:
        """身份、版本和两类文本完整时应生成无正文摘要。"""
        audit = audit_records(
            records=[build_record()],
            user_id=9,
            file_id="file-a",
            index_version=3,
            expected_count=1,
        )

        self.assertEqual(audit["chunk_count"], 1)
        self.assertEqual(audit["parent_count"], 1)
        self.assertRegex(audit["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("child text", audit["content_sha256"])

    def test_audit_rejects_missing_parent_text(self) -> None:
        """没有 parent_content 时 migration 011 不应获得审计证明。"""
        with self.assertRaisesRegex(CutoverError, "parent_content"):
            audit_records(
                records=[build_record(parent_content="")],
                user_id=9,
                file_id="file-a",
                index_version=3,
                expected_count=1,
            )

    def test_audit_rejects_stale_index_version(self) -> None:
        """旧版本 entities 不能为当前文件版本放行。"""
        with self.assertRaisesRegex(CutoverError, "index_version"):
            audit_records(
                records=[build_record(index_version=2)],
                user_id=9,
                file_id="file-a",
                index_version=3,
                expected_count=1,
            )

    def test_digest_is_stable_independent_of_query_order(self) -> None:
        """Milvus 返回顺序变化不应改变 cutover 摘要。"""
        first = build_record(child_id="9:file-a:v3:p0:c0")
        second = build_record(child_id="9:file-a:v3:p0:c1")

        self.assertEqual(
            build_content_digest([first, second]),
            build_content_digest([second, first]),
        )


if __name__ == "__main__":
    unittest.main()
