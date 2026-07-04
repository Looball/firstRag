from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import demo_cleanup


class DemoCleanupScriptTests(unittest.TestCase):
    """demo cleanup 脚本测试。"""

    def test_retained_knowledge_base_protects_owner_and_linked_files(self) -> None:
        """保留样例知识库时，应保护 owner 用户和关联文件不被清理。"""
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        retained_kb_id = str(uuid4())
        linked_file_id = str(uuid4())
        stale_kb_id = str(uuid4())
        stale_file_id = str(uuid4())
        stale_conversation_id = str(uuid4())
        snapshot = demo_cleanup.DatabaseSnapshot(
            users=[
                {"id": 1, "username": "demo", "created_at": old_time},
                {"id": 2, "username": "temp", "created_at": old_time},
            ],
            knowledge_bases=[
                {
                    "id": retained_kb_id,
                    "user_id": 1,
                    "name": "sample",
                    "created_at": old_time,
                },
                {
                    "id": stale_kb_id,
                    "user_id": 1,
                    "name": "scratch",
                    "created_at": old_time,
                },
            ],
            knowledge_files=[
                {
                    "id": linked_file_id,
                    "user_id": 1,
                    "storage_path": "/app/uploads/users/1/a/b/file/source.md",
                    "created_at": old_time,
                },
                {
                    "id": stale_file_id,
                    "user_id": 1,
                    "storage_path": "/app/uploads/users/1/c/d/file/source.md",
                    "created_at": old_time,
                },
            ],
            knowledge_base_files=[
                {
                    "knowledge_base_id": retained_kb_id,
                    "knowledge_file_id": linked_file_id,
                    "created_at": old_time,
                }
            ],
            conversations=[
                {
                    "id": stale_conversation_id,
                    "user_id": 1,
                    "knowledge_base_id": retained_kb_id,
                    "created_at": old_time,
                }
            ],
        )
        retention = demo_cleanup.RetentionConfig(
            retain_user_ids=set(),
            retain_knowledge_base_ids={retained_kb_id},
            retain_file_ids=set(),
            cleanup_user_ids=set(),
            cutoff=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        selection = demo_cleanup.build_cleanup_selection(snapshot, retention)

        self.assertEqual(selection.retained_user_ids, {1})
        self.assertIn(linked_file_id, selection.retained_file_ids)
        self.assertNotIn(1, selection.cleanup_user_ids)
        self.assertIn(2, selection.cleanup_user_ids)
        self.assertNotIn(retained_kb_id, selection.cleanup_knowledge_base_ids)
        self.assertIn(stale_kb_id, selection.cleanup_knowledge_base_ids)
        self.assertNotIn(linked_file_id, selection.cleanup_file_ids)
        self.assertIn(stale_file_id, selection.cleanup_file_ids)
        self.assertIn(stale_conversation_id, selection.cleanup_conversation_ids)

    def test_resolve_upload_target_translates_container_path(self) -> None:
        """容器内 /app/uploads 路径应映射到配置的 uploads 根目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            uploads_dir = Path(tmpdir) / "uploads"
            uploads_dir.mkdir()

            resolved_path, reason = demo_cleanup.resolve_upload_target_path(
                "/app/uploads/users/1/ab/cd/file-id/source.md",
                uploads_dir,
            )

        self.assertIsNone(reason)
        self.assertEqual(
            resolved_path,
            (uploads_dir / "users/1/ab/cd/file-id/source.md").resolve(),
        )

    def test_cleanup_user_id_must_exist(self) -> None:
        """显式清理不存在的用户 ID 应直接报错，避免审计摘要失真。"""
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        snapshot = demo_cleanup.DatabaseSnapshot(
            users=[{"id": 1, "username": "demo", "created_at": old_time}],
            knowledge_bases=[],
            knowledge_files=[],
            knowledge_base_files=[],
            conversations=[],
        )
        retention = demo_cleanup.RetentionConfig(
            retain_user_ids=set(),
            retain_knowledge_base_ids=set(),
            retain_file_ids=set(),
            cleanup_user_ids={404},
            cutoff=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        with self.assertRaisesRegex(demo_cleanup.DemoCleanupError, "清理用户不存在"):
            demo_cleanup.build_cleanup_selection(snapshot, retention)

    def test_resolve_upload_target_rejects_path_outside_uploads(self) -> None:
        """上传文件删除目标必须限制在 uploads 根目录内。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            uploads_dir = Path(tmpdir) / "uploads"
            uploads_dir.mkdir()

            resolved_path, reason = demo_cleanup.resolve_upload_target_path(
                "/etc/passwd",
                uploads_dir,
            )

        self.assertIsNone(resolved_path)
        self.assertIn("uploads", reason or "")


if __name__ == "__main__":
    unittest.main()
