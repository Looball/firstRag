"""PostgreSQL parent/child chunk 生命周期回归测试。"""

import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.repositories.knowledge_chunk_repository import (
    delete_file_chunks,
    get_user_parent_chunks,
    replace_file_chunks,
)


class KnowledgeChunkParentChildRepositoryTests(unittest.TestCase):
    """验证父子块在同一事务内替换、校验和删除。"""

    def test_replace_writes_parent_before_child_in_one_connection(self) -> None:
        """父块必须先写入，child 外键随后在同一连接内写入。"""
        parent_id = "7:file-a:v3:p0"
        parent = Document(
            page_content="完整父块",
            metadata={
                "user_id": "7",
                "file_id": "file-a",
                "index_version": 3,
                "parent_index": 0,
                "parent_id": parent_id,
            },
        )
        child = Document(
            page_content="精确子块",
            metadata={
                "user_id": "7",
                "file_id": "file-a",
                "index_version": 3,
                "parent_id": parent_id,
                "parent_index": 0,
                "child_index": 0,
                "chunk_index": 0,
            },
        )
        connection_context = MagicMock()
        connection = connection_context.__enter__.return_value
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.rowcount = 1

        with patch(
            "app.repositories.knowledge_chunk_repository.get_connection",
            return_value=connection_context,
        ):
            inserted = replace_file_chunks(
                user_id=7,
                file_id="file-a",
                index_version=3,
                chunks=[child],
                chunk_ids=[f"{parent_id}:c0"],
                parents=[parent],
                parent_ids=[parent_id],
            )

        self.assertEqual(inserted, 1)
        self.assertEqual(cursor.executemany.call_count, 2)
        parent_sql = cursor.executemany.call_args_list[0].args[0]
        child_sql = cursor.executemany.call_args_list[1].args[0]
        self.assertIn("INSERT INTO knowledge_file_chunk_parents", parent_sql)
        self.assertIn("INSERT INTO knowledge_file_chunks", child_sql)
        child_row = cursor.executemany.call_args_list[1].args[1][0]
        self.assertEqual(child_row[5:7], (parent_id, 0))

    def test_replace_rejects_orphan_child_before_opening_connection(self) -> None:
        """child 引用未写入 parent 时必须在数据库操作前失败。"""
        child = Document(
            page_content="orphan",
            metadata={
                "chunk_index": 0,
                "child_index": 0,
                "parent_id": "missing-parent",
            },
        )
        parent = Document(
            page_content="parent",
            metadata={"parent_index": 0},
        )
        with patch(
            "app.repositories.knowledge_chunk_repository.get_connection",
        ) as get_connection:
            with self.assertRaisesRegex(ValueError, "parent_id"):
                replace_file_chunks(
                    user_id=7,
                    file_id="file-a",
                    index_version=3,
                    chunks=[child],
                    chunk_ids=["child"],
                    parents=[parent],
                    parent_ids=["expected-parent"],
                )

        get_connection.assert_not_called()

    def test_delete_removes_children_before_parents(self) -> None:
        """删除顺序应先 child 后 parent，满足外键生命周期。"""
        connection_context = MagicMock()
        connection = connection_context.__enter__.return_value
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.rowcount = 2

        with patch(
            "app.repositories.knowledge_chunk_repository.get_connection",
            return_value=connection_context,
        ):
            deleted_children = delete_file_chunks(7, "file-a")

        self.assertEqual(deleted_children, 2)
        executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("DELETE FROM knowledge_file_chunks", executed_sql[0])
        self.assertIn(
            "DELETE FROM knowledge_file_chunk_parents",
            executed_sql[1],
        )

    def test_parent_context_batch_query_enforces_user_and_soft_delete(self) -> None:
        """parent 扩展查询必须同时限制 user、parent IDs 与有效文件。"""
        with patch(
            "app.repositories.knowledge_chunk_repository.fetch_all",
            return_value=[{"parent_id": "parent-a"}],
        ) as fetch_all:
            rows = get_user_parent_chunks(7, ["parent-a", "", "parent-a"])

        self.assertEqual(rows, [{"parent_id": "parent-a"}])
        sql, params = fetch_all.call_args.args
        self.assertIn("parent.parent_id = ANY(%s::text[])", sql)
        self.assertIn("parent.user_id = %s", sql)
        self.assertIn("file.deleted_at IS NULL", sql)
        self.assertEqual(params, (7, ["parent-a"]))


if __name__ == "__main__":
    unittest.main()
