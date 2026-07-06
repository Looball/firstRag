"""向量化任务 worker 的回归测试。"""

import io
import json
import unittest
from contextlib import contextmanager, redirect_stdout
from types import SimpleNamespace
from uuid import uuid4

from app.workers.vector_index_worker import process_next_vector_index_job


class NoopHeartbeatLoop:
    """测试中替代后台 heartbeat thread，避免访问 Redis。"""

    def __init__(self, *args, **kwargs) -> None:
        """接收真实 heartbeat loop 的参数。"""

    def __enter__(self) -> "NoopHeartbeatLoop":
        """进入 no-op context。"""
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """退出 no-op context。"""


class VectorIndexWorkerLoggingTests(unittest.TestCase):
    """验证 worker 处理任务时使用日志而不是 stdout。"""

    @contextmanager
    def patch_worker_runtime(self, lock=None):
        """隔离 Redis worker runtime，避免单元测试访问外部服务。"""
        lock_result = lock or SimpleNamespace(
            is_busy=False,
            available=True,
            fallback_reason=None,
            owner_job_id=None,
            acquired=True,
        )
        with unittest.mock.patch(
            "app.workers.vector_index_worker.record_worker_heartbeat",
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.record_worker_job_event",
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.acquire_file_processing_lock",
            return_value=lock_result,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.release_file_processing_lock",
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.WorkerHeartbeatLoop",
            NoopHeartbeatLoop,
        ):
            yield lock_result

    def test_process_indexed_file_job_does_not_print(self) -> None:
        """已完成索引的重复任务应安静跳过并标记成功。"""
        job_id = uuid4()
        file_id = uuid4()
        job = {
            "id": job_id,
            "user_id": 1,
            "knowledge_file_id": file_id,
            "index_version": 2,
        }
        file_record = {
            "id": file_id,
            "status": "indexed",
            "index_version": 2,
        }

        with unittest.mock.patch(
            "app.workers.vector_index_worker.reclaim_expired_vector_index_jobs",
            return_value=0,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.claim_next_vector_index_job",
            return_value=job,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.get_user_knowledge_file",
            return_value=file_record,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.mark_vector_index_job_succeeded",
        ) as mark_succeeded, self.patch_worker_runtime():
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                processed = process_next_vector_index_job("worker-1")

        self.assertTrue(processed)
        self.assertEqual(stdout.getvalue(), "")
        mark_succeeded.assert_called_once()

    def test_process_failed_job_logs_exception_without_printing(self) -> None:
        """任务失败时应记录异常日志并标记失败，不直接写 stdout。"""
        job_id = uuid4()
        file_id = uuid4()
        job = {
            "id": job_id,
            "user_id": 1,
            "knowledge_file_id": file_id,
            "index_version": 1,
        }

        with unittest.mock.patch(
            "app.workers.vector_index_worker.reclaim_expired_vector_index_jobs",
            return_value=0,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.claim_next_vector_index_job",
            return_value=job,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.get_user_knowledge_file",
            side_effect=RuntimeError("boom"),
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.mark_vector_index_job_failed",
        ) as mark_failed, self.assertLogs(
            "app.workers.vector_index_worker",
            level="ERROR",
        ) as logs, self.patch_worker_runtime():
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                processed = process_next_vector_index_job("worker-1")

        self.assertTrue(processed)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("向量化任务失败", "\n".join(logs.output))
        failed_payload = json.loads(logs.records[-1].getMessage())
        self.assertEqual(failed_payload["event"], "vector_index_job_failed")
        self.assertEqual(failed_payload["error_source"], "worker")
        self.assertEqual(failed_payload["job_id"], str(job_id))
        mark_failed.assert_called_once_with(job_id, "boom")

    def test_process_empty_document_failure_marks_job_failed(self) -> None:
        """空文档解析结果应稳定落入失败状态，便于前端展示和重试。"""
        job_id = uuid4()
        file_id = uuid4()
        job = {
            "id": job_id,
            "user_id": 1,
            "knowledge_file_id": file_id,
            "index_version": 1,
        }
        file_record = {
            "id": file_id,
            "status": "pending",
            "index_version": 1,
        }
        error_message = "文件为空，未解析出可入库的文本分块"

        with unittest.mock.patch(
            "app.workers.vector_index_worker.reclaim_expired_vector_index_jobs",
            return_value=0,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.claim_next_vector_index_job",
            return_value=job,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.get_user_knowledge_file",
            return_value=file_record,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.index_knowledge_file_record",
            side_effect=ValueError(error_message),
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.mark_vector_index_job_failed",
        ) as mark_failed, self.assertLogs(
            "app.workers.vector_index_worker",
            level="ERROR",
        ), self.patch_worker_runtime():
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                processed = process_next_vector_index_job("worker-1")

        self.assertTrue(processed)
        self.assertEqual(stdout.getvalue(), "")
        mark_failed.assert_called_once_with(job_id, error_message)

    def test_lock_busy_defers_job_without_processing_file(self) -> None:
        """Redis 短租约被占用时应短暂退回队列，避免重复索引。"""
        job_id = uuid4()
        file_id = uuid4()
        job = {
            "id": job_id,
            "user_id": 1,
            "knowledge_file_id": file_id,
            "index_version": 1,
        }
        busy_lock = SimpleNamespace(
            is_busy=True,
            available=True,
            fallback_reason=None,
            owner_job_id="other-job",
            acquired=False,
        )

        with unittest.mock.patch(
            "app.workers.vector_index_worker.reclaim_expired_vector_index_jobs",
            return_value=0,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.claim_next_vector_index_job",
            return_value=job,
        ), unittest.mock.patch(
            "app.workers.vector_index_worker.defer_vector_index_job",
        ) as defer_job, unittest.mock.patch(
            "app.workers.vector_index_worker.get_user_knowledge_file",
        ) as get_file, self.patch_worker_runtime(busy_lock):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                processed = process_next_vector_index_job("worker-1")

        self.assertTrue(processed)
        self.assertEqual(stdout.getvalue(), "")
        defer_job.assert_called_once()
        get_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
