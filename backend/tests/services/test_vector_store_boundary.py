"""provider-neutral vector store boundary 契约测试。"""

import unittest

from langchain_core.documents import Document

from app.services.vectors.chroma_vector_store import ChromaVectorStore
from app.services.vectors.vector_store import VectorStoreProviderError


def matches_filter(metadata: dict[str, object], where: dict) -> bool:
    """为测试 fake 执行 Chroma 等值与 $and filter。"""
    if "$and" in where:
        return all(matches_filter(metadata, item) for item in where["$and"])
    return all(str(metadata.get(key)) == str(value) for key, value in where.items())


class FakeCollection:
    """保存在内存中的最小 Chroma collection fake。"""

    name = "test-collection"

    def __init__(self, client: "FakeChromaClient") -> None:
        """绑定记录所属 client。"""
        self.client = client

    def count(self) -> int:
        """返回当前记录总数。"""
        return len(self.client.records)

    def get(self, *, where: dict, include: list[str]) -> dict[str, object]:
        """按 metadata filter 返回审计字段。"""
        rows = [
            row
            for row in self.client.records.values()
            if matches_filter(row["document"].metadata, where)
        ]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"].page_content for row in rows],
            "metadatas": [row["document"].metadata for row in rows],
            "embeddings": [row["embedding"] for row in rows]
            if "embeddings" in include
            else None,
        }


class FakeChromaClient:
    """支持写入、删除、过滤检索的 LangChain Chroma fake。"""

    def __init__(self) -> None:
        """初始化空记录和 collection。"""
        self.records: dict[str, dict] = {}
        self._collection = FakeCollection(self)

    def delete(self, *, where: dict) -> None:
        """仅删除符合用户和文件过滤条件的记录。"""
        self.records = {
            record_id: row
            for record_id, row in self.records.items()
            if not matches_filter(row["document"].metadata, where)
        }

    def add_documents(
        self,
        *,
        documents: list[Document],
        ids: list[str],
    ) -> None:
        """按稳定 ID 覆盖写入记录。"""
        for record_id, document in zip(ids, documents, strict=True):
            score = float(document.metadata.get("test_distance", 0.5))
            self.records[record_id] = {
                "id": record_id,
                "document": document,
                "embedding": [1.0 - score, score],
                "distance": score,
            }

    def similarity_search_by_vector_with_relevance_scores(
        self,
        *,
        embedding: list[float],
        k: int,
        filter: dict | None = None,
    ) -> list[tuple[Document, float]]:
        """按 filter 返回故意未排序的候选，验证 adapter 排序。"""
        del embedding
        rows = list(reversed(list(self.records.values())))
        if filter is not None:
            rows = [
                row
                for row in rows
                if matches_filter(row["document"].metadata, filter)
            ]
        return [
            (row["document"], row["distance"])
            for row in rows[:k]
        ]


def make_document(
    *,
    content: str,
    user_id: int,
    file_id: str,
    distance: float,
) -> Document:
    """创建带隔离字段与测试 distance 的文档。"""
    return Document(
        page_content=content,
        metadata={
            "user_id": str(user_id),
            "file_id": file_id,
            "chunk_index": 0,
            "index_version": 0,
            "test_distance": distance,
        },
    )


class VectorStoreBoundaryTests(unittest.TestCase):
    """验证 Chroma adapter 遵守统一业务契约。"""

    def setUp(self) -> None:
        """为每个测试创建独立 adapter。"""
        self.client = FakeChromaClient()
        self.store = ChromaVectorStore(self.client, "test-collection")

    def test_replace_is_idempotent_and_delete_is_user_file_scoped(self) -> None:
        """重复替换不应累加，删除不得越过用户和文件边界。"""
        first = make_document(
            content="旧内容",
            user_id=1,
            file_id="shared-file",
            distance=0.4,
        )
        other_user = make_document(
            content="其它用户",
            user_id=2,
            file_id="shared-file",
            distance=0.2,
        )
        self.store.replace_file_vectors(
            user_id=1,
            file_id="shared-file",
            documents=[first],
            ids=["1:shared-file:v0:0"],
        )
        self.store.replace_file_vectors(
            user_id=2,
            file_id="shared-file",
            documents=[other_user],
            ids=["2:shared-file:v0:0"],
        )
        replacement = make_document(
            content="新内容",
            user_id=1,
            file_id="shared-file",
            distance=0.1,
        )
        self.store.replace_file_vectors(
            user_id=1,
            file_id="shared-file",
            documents=[replacement],
            ids=["1:shared-file:v1:0"],
        )

        self.assertEqual(self.store.count_vectors(), 2)
        self.assertEqual(
            self.store.list_file_vectors(
                user_id=1,
                file_id="shared-file",
            )[0].document.page_content,
            "新内容",
        )
        self.store.delete_file_vectors(user_id=1, file_id="shared-file")
        self.assertEqual(self.store.count_vectors(), 1)
        self.assertEqual(
            self.store.count_vectors(user_id=2, file_id="shared-file"),
            1,
        )

    def test_search_enforces_scope_and_normalizes_sort_order(self) -> None:
        """搜索只返回指定用户/文件，并按 distance 升序输出。"""
        fixtures = [
            ("user-one-a", 1, "a", 0.3),
            ("user-one-b", 1, "b", 0.1),
            ("other-user", 2, "a", 0.01),
            ("other-file", 1, "c", 0.02),
        ]
        for index, (content, user_id, file_id, distance) in enumerate(fixtures):
            self.store.replace_file_vectors(
                user_id=user_id,
                file_id=file_id,
                documents=[make_document(
                    content=content,
                    user_id=user_id,
                    file_id=file_id,
                    distance=distance,
                )],
                ids=[f"record-{index}"],
            )

        response = self.store.search_vectors(
            query_embedding=[1.0, 0.0],
            user_id=1,
            file_ids=["a", "b"],
            k=5,
        )

        self.assertEqual(
            [result.document.page_content for result in response.results],
            ["user-one-b", "user-one-a"],
        )
        self.assertEqual(
            [result.distance for result in response.results],
            [0.1, 0.3],
        )
        self.assertEqual(response.issues, [])

    def test_audit_health_and_provider_error_are_provider_neutral(self) -> None:
        """审计、健康和异常均通过稳定契约暴露。"""
        document = make_document(
            content="可审计记录",
            user_id=1,
            file_id="audit-file",
            distance=0.25,
        )
        self.store.replace_file_vectors(
            user_id=1,
            file_id="audit-file",
            documents=[document],
            ids=["audit-id"],
        )

        records = self.store.list_file_vectors(
            user_id=1,
            file_id="audit-file",
            include_embeddings=True,
        )
        self.assertEqual(records[0].id, "audit-id")
        self.assertEqual(records[0].embedding, [0.75, 0.25])
        self.assertTrue(self.store.health_check().healthy)
        self.assertEqual(self.store.ensure_collection(), "test-collection")

        self.client.similarity_search_by_vector_with_relevance_scores = (
            lambda **_: (_ for _ in ()).throw(
                TimeoutError("connection timeout api_key=secret"),
            )
        )
        with self.assertRaises(VectorStoreProviderError) as raised:
            self.store.search_vectors(
                query_embedding=[1.0, 0.0],
                user_id=1,
                file_ids=None,
                k=1,
            )
        self.assertEqual(raised.exception.provider, "chroma")
        self.assertEqual(raised.exception.category, "unavailable")
        self.assertEqual(raised.exception.operation, "search_vectors")
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
