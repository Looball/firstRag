"""知识文件接口的回归测试。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limits
from app.core.security import get_current_user_id
from app.main import app
from app.services.file_service import FileTooLargeError


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f"
    b"\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class KnowledgeFileListTests(unittest.TestCase):
    """验证文件列表返回向量化任务状态。"""

    def setUp(self) -> None:
        """为每个测试注入固定认证用户。"""
        reset_rate_limits()
        app.dependency_overrides[get_current_user_id] = lambda: 1
        self.quota_usage_patcher = patch(
            "app.api.knowledge_files.get_user_file_quota_usage",
            return_value={"file_count": 0, "total_size_bytes": 0},
        )
        self.get_user_file_quota_usage = self.quota_usage_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """清理依赖覆盖，避免影响其他路由。"""
        self.quota_usage_patcher.stop()
        app.dependency_overrides.clear()
        self.client.close()
        reset_rate_limits()

    def test_get_knowledge_base_files_returns_latest_index_job(self) -> None:
        """知识库文件列表应返回每个文件最近一次向量化任务。"""
        knowledge_base_id = uuid4()
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_bases.get_knowledge_base_file_records",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "failed",
                    "index_version": 0,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:01+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_bases.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": knowledge_base_id,
                    "index_version": 0,
                    "status": "failed",
                    "attempts": 3,
                    "max_attempts": 3,
                    "error_message": "解析失败",
                    "result": None,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                    "started_at": "2026-06-25T00:00:01+08:00",
                    "finished_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
            )

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "failed")
        self.assertEqual(latest_job["error_message"], "文件解析失败")
        self.assertEqual(latest_job["failure_type"], "parse_error")
        self.assertEqual(
            latest_job["failure_hint"],
            "文件解析失败。请确认文件内容可读取，必要时转为 PDF、Markdown、TXT 或支持的图片格式后重新上传。",
        )
        self.assertTrue(latest_job["can_retry"])
        self.assertEqual(latest_job["attempts"], 3)

    def test_get_all_knowledge_files_returns_latest_index_job(self) -> None:
        """全局文件列表也应返回最近一次向量化任务。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "queued",
                    "index_version": 0,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 0,
                    "status": "queued",
                    "attempts": 0,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": None,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:00+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "queued")
        self.assertEqual(latest_job["max_attempts"], 3)

    def test_latest_index_job_includes_stale_worker_hint(self) -> None:
        """文件列表应返回单文件向量化卡住提示。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "queued",
                    "index_version": 0,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 0,
                    "status": "queued",
                    "attempts": 0,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": None,
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:00+08:00",
                    "active_seconds": 1800,
                    "is_stale": True,
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertTrue(latest_job["is_stale"])
        self.assertEqual(latest_job["active_seconds"], 1800)
        self.assertEqual(
            latest_job["worker_hint"],
            "该文件向量化任务长时间排队，可能 worker 未启动。",
        )

    def test_latest_index_job_normalizes_succeeded_status(self) -> None:
        """文件列表应把内部 succeeded 状态归一化为前端协议的 completed。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "indexed",
                    "index_version": 1,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 1,
                    "status": "succeeded",
                    "attempts": 1,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": {"chunk_count": 3},
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                    "started_at": "2026-06-25T00:00:01+08:00",
                    "finished_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        latest_job = response.json()["files"][0]["latest_index_job"]
        self.assertEqual(latest_job["id"], str(job_id))
        self.assertEqual(latest_job["status"], "completed")

    def test_stale_index_job_is_hidden_after_vector_delete(self) -> None:
        """删除向量后，旧版本成功任务不应继续让前端显示已向量化。"""
        file_id = uuid4()
        job_id = uuid4()
        with patch(
            "app.api.knowledge_files.get_user_knowledge_files",
            return_value=[
                {
                    "id": file_id,
                    "original_name": "demo.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 123,
                    "status": "pending",
                    "index_version": 2,
                    "usage_count": 1,
                    "created_at": "2026-06-25T00:00:00+08:00",
                }
            ],
        ), patch(
            "app.api.knowledge_files.get_latest_vector_index_jobs_by_file_ids",
            return_value={
                str(file_id): {
                    "id": job_id,
                    "user_id": 1,
                    "knowledge_file_id": file_id,
                    "knowledge_base_id": None,
                    "index_version": 1,
                    "status": "succeeded",
                    "attempts": 1,
                    "max_attempts": 3,
                    "error_message": None,
                    "result": {"chunk_count": 3},
                    "created_at": "2026-06-25T00:00:00+08:00",
                    "updated_at": "2026-06-25T00:00:02+08:00",
                }
            },
        ):
            response = self.client.get("/chat/knowledge-files")

        self.assertEqual(response.status_code, 200)
        file_payload = response.json()["files"][0]
        self.assertEqual(file_payload["status"], "pending")
        self.assertIsNone(file_payload["latest_index_job"])

    def test_upload_rejects_unsupported_file_extension(self) -> None:
        """上传入口应在创建文件记录前拒绝不支持的文件类型。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
        ) as calculate_file_hash, patch(
            "app.api.knowledge_files.create_file_with_relation",
        ) as create_file:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "malware.exe",
                        b"not a document",
                        "application/octet-stream",
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文件类型", response.json()["detail"])
        calculate_file_hash.assert_not_called()
        create_file.assert_not_called()

    def test_upload_rejects_supported_extension_with_unsafe_mime(self) -> None:
        """扩展名支持但 MIME 明显不匹配时也应拒绝。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
        ) as calculate_file_hash:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "image/png",
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文件类型", response.json()["detail"])
        calculate_file_hash.assert_not_called()

    def test_upload_rejects_image_with_invalid_content(self) -> None:
        """图片扩展名和 MIME 合法时，上传阶段仍应校验文件头。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("hash", 12),
        ), patch(
            "app.api.knowledge_files.create_file_with_relation",
        ) as create_file:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "chart.png",
                        b"not an image",
                        "image/png",
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("无法识别图片格式", response.json()["detail"])
        create_file.assert_not_called()

    def test_upload_rejects_oversized_supported_file(self) -> None:
        """超过大小限制的合法类型文件应稳定返回 413。"""
        knowledge_base_id = uuid4()
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            side_effect=FileTooLargeError("文件超过 200MB 限制"),
        ), patch(
            "app.api.knowledge_files.create_file_with_relation",
        ) as create_file:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "large.pdf",
                        b"%PDF-1.7",
                        "application/pdf",
                    )
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"detail": "文件超过 200MB 限制"})
        create_file.assert_not_called()

    def test_upload_rejects_when_file_count_quota_exceeded(self) -> None:
        """新增文件超过用户文件数量配额时应返回清晰提示。"""
        knowledge_base_id = uuid4()
        self.get_user_file_quota_usage.return_value = {
            "file_count": 2,
            "total_size_bytes": 1024,
        }
        with patch(
            "app.api.knowledge_files.USER_UPLOAD_MAX_FILES",
            2,
        ), patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("new-hash", 7),
        ), patch(
            "app.api.knowledge_files.get_file_by_hash",
            return_value=None,
        ), patch(
            "app.api.knowledge_files.create_file_with_relation",
        ) as create_file:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "text/markdown",
                    )
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("上传文件数量已达上限", response.json()["detail"])
        create_file.assert_not_called()

    def test_upload_rejects_when_storage_quota_exceeded(self) -> None:
        """新增文件超过用户容量配额时应返回 413。"""
        knowledge_base_id = uuid4()
        self.get_user_file_quota_usage.return_value = {
            "file_count": 1,
            "total_size_bytes": 90,
        }
        with patch(
            "app.api.knowledge_files.USER_UPLOAD_MAX_FILES",
            10,
        ), patch(
            "app.api.knowledge_files.USER_UPLOAD_MAX_BYTES",
            100,
        ), patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("new-hash", 20),
        ), patch(
            "app.api.knowledge_files.get_file_by_hash",
            return_value=None,
        ), patch(
            "app.api.knowledge_files.create_file_with_relation",
        ) as create_file:
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "text/markdown",
                    )
                },
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("上传容量配额不足", response.json()["detail"])
        create_file.assert_not_called()

    def test_upload_is_rate_limited_before_file_hashing(self) -> None:
        """上传接口高频调用应在读取文件内容前返回 429。"""
        knowledge_base_id = uuid4()
        file_id = uuid4()
        existing_file = {
            "id": file_id,
            "original_name": "notes.md",
            "mime_type": "text/markdown",
            "size_bytes": 7,
            "status": "pending",
            "index_version": 0,
            "created_at": "2026-06-29T00:00:00+08:00",
            "updated_at": "2026-06-29T00:00:00+08:00",
        }
        with patch(
            "app.api.knowledge_files.UPLOAD_RATE_LIMIT_MAX_REQUESTS",
            1,
        ), patch(
            "app.api.knowledge_files.API_RATE_LIMIT_WINDOW_SECONDS",
            60,
        ), patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("hash", 7),
        ) as calculate_file_hash, patch(
            "app.api.knowledge_files.get_file_by_hash",
            return_value=existing_file,
        ), patch(
            "app.api.knowledge_files.add_existing_file_relation",
            return_value=True,
        ):
            first = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "text/markdown",
                    )
                },
            )
            second = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "text/markdown",
                    )
                },
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(
            second.json(),
            {"detail": "上传请求过于频繁，请稍后再试。"},
        )
        calculate_file_hash.assert_called_once()

    def test_upload_allows_supported_markdown_file(self) -> None:
        """支持类型仍应走原有复用和关联流程。"""
        knowledge_base_id = uuid4()
        file_id = uuid4()
        existing_file = {
            "id": file_id,
            "original_name": "notes.md",
            "mime_type": "text/markdown",
            "size_bytes": 7,
            "status": "pending",
            "index_version": 0,
            "created_at": "2026-06-29T00:00:00+08:00",
            "updated_at": "2026-06-29T00:00:00+08:00",
        }
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("hash", 7),
        ) as calculate_file_hash, patch(
            "app.api.knowledge_files.get_file_by_hash",
            return_value=existing_file,
        ), patch(
            "app.api.knowledge_files.add_existing_file_relation",
            return_value=True,
        ):
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "notes.md",
                        b"# title",
                        "text/markdown",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["files"][0]["reused"])
        calculate_file_hash.assert_called_once()

    def test_upload_allows_supported_png_file(self) -> None:
        """知识库上传入口应允许真实 PNG 图片文件。"""
        knowledge_base_id = uuid4()
        file_id = uuid4()
        existing_file = {
            "id": file_id,
            "original_name": "chart.png",
            "mime_type": "image/png",
            "size_bytes": len(PNG_BYTES),
            "status": "pending",
            "index_version": 0,
            "created_at": "2026-07-05T00:00:00+08:00",
            "updated_at": "2026-07-05T00:00:00+08:00",
        }
        with patch(
            "app.api.knowledge_files.knowledge_base_exists",
            return_value=True,
        ), patch(
            "app.api.knowledge_files.calculate_file_hash",
            return_value=("hash", len(PNG_BYTES)),
        ) as calculate_file_hash, patch(
            "app.api.knowledge_files.get_file_by_hash",
            return_value=existing_file,
        ), patch(
            "app.api.knowledge_files.add_existing_file_relation",
            return_value=True,
        ):
            response = self.client.post(
                f"/chat/knowledge-base/{knowledge_base_id}/files",
                files={
                    "files": (
                        "chart.png",
                        PNG_BYTES,
                        "image/png",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["files"][0]["mime_type"], "image/png")
        calculate_file_hash.assert_called_once()


if __name__ == "__main__":
    unittest.main()
