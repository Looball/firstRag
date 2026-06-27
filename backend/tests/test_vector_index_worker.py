"""向量化任务 worker 的回归测试。"""

import io
import unittest
from contextlib import redirect_stdout
from uuid import uuid4

from app.workers.vector_index_worker import process_next_vector_index_job


class VectorIndexWorkerLoggingTests(unittest.TestCase):
    """验证 worker 处理任务时使用日志而不是 stdout。"""

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
        ) as mark_succeeded:
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
        ) as logs:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                processed = process_next_vector_index_job("worker-1")

        self.assertTrue(processed)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("向量化任务失败", "\n".join(logs.output))
        mark_failed.assert_called_once_with(job_id, "boom")


if __name__ == "__main__":
    unittest.main()
