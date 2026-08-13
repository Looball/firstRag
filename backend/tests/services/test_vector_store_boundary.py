"""Provider-neutral vector store 契约回归测试。"""

import unittest
from uuid import UUID

from langchain_core.documents import Document

from app.services.vectors.vector_store import (
    VectorRecord,
    VectorSearchResponse,
    VectorStoreBoundary,
    VectorStoreHealth,
    build_chunk_ids,
    build_parent_ids,
)


class FakeVectorStore:
    """实现完整契约的最小测试 vector store。"""

    provider = "fake"
    collection_name = "fake_collection"

    def ensure_collection(self) -> str:
        """返回测试 collection。"""
        return self.collection_name

    def replace_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        documents: list[Document],
        ids: list[str],
    ) -> None:
        """测试 fake 不持久化数据。"""

    def delete_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """测试 fake 不持久化数据。"""

    def delete_current_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
    ) -> None:
        """测试 fake 不持久化当前 identity 数据。"""

    def search_vectors(
        self,
        *,
        query_embedding: list[float],
        user_id: int,
        file_ids: list[UUID | str] | None,
        k: int,
    ) -> VectorSearchResponse:
        """返回空检索结果。"""
        return VectorSearchResponse()

    def list_file_vectors(
        self,
        *,
        user_id: int,
        file_id: UUID | str,
        include_embeddings: bool = False,
    ) -> list[VectorRecord]:
        """返回空审计结果。"""
        return []

    def count_vectors(
        self,
        *,
        user_id: int | None = None,
        file_id: UUID | str | None = None,
    ) -> int:
        """返回空计数。"""
        return 0

    def health_check(self) -> VectorStoreHealth:
        """返回健康测试结果。"""
        return VectorStoreHealth(
            healthy=True,
            provider=self.provider,
            collection_name=self.collection_name,
        )


class VectorStoreBoundaryTests(unittest.TestCase):
    """验证业务层只接受统一 vector store 契约。"""

    def test_complete_implementation_matches_runtime_protocol(self) -> None:
        """实现完整 Protocol 的 adapter 应匹配 runtime contract。"""
        self.assertIsInstance(FakeVectorStore(), VectorStoreBoundary)

    def test_raw_provider_client_does_not_match_runtime_protocol(self) -> None:
        """原始 provider client 不应匹配业务层 contract。"""
        self.assertNotIsInstance(object(), VectorStoreBoundary)

    def test_chunk_ids_are_stable_across_provider_changes(self) -> None:
        """向量 ID 只由业务 metadata 决定。"""
        chunks = [
            Document(
                page_content="first",
                metadata={
                    "user_id": 7,
                    "file_id": "00000000-0000-0000-0000-000000000001",
                    "index_version": 3,
                    "chunk_index": 0,
                    "parent_index": 0,
                    "child_index": 0,
                },
            ),
            Document(
                page_content="second",
                metadata={
                    "user_id": 7,
                    "file_id": "00000000-0000-0000-0000-000000000001",
                    "index_version": 3,
                    "chunk_index": 1,
                    "parent_index": 0,
                    "child_index": 1,
                },
            ),
        ]

        self.assertEqual(
            build_chunk_ids(chunks),
            [
                "7:00000000-0000-0000-0000-000000000001:v3:p0:c0",
                "7:00000000-0000-0000-0000-000000000001:v3:p0:c1",
            ],
        )
        self.assertEqual(
            chunks[0].metadata["parent_id"],
            "7:00000000-0000-0000-0000-000000000001:v3:p0",
        )
        self.assertEqual(
            chunks[1].metadata["child_id"],
            "7:00000000-0000-0000-0000-000000000001:v3:p0:c1",
        )

    def test_parent_ids_are_stable_and_written_to_metadata(self) -> None:
        """父块 ID 应包含用户、文件、版本与 parent 序号。"""
        parent = Document(
            page_content="parent",
            metadata={
                "user_id": 7,
                "file_id": "00000000-0000-0000-0000-000000000001",
                "index_version": 3,
                "parent_index": 2,
            },
        )

        self.assertEqual(
            build_parent_ids([parent]),
            ["7:00000000-0000-0000-0000-000000000001:v3:p2"],
        )
        self.assertEqual(
            parent.metadata["parent_id"],
            "7:00000000-0000-0000-0000-000000000001:v3:p2",
        )


if __name__ == "__main__":
    unittest.main()
