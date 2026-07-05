import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_indexing


class EvalIndexingScriptTests(unittest.TestCase):
    """上传与向量化验收脚本测试。"""

    def build_chat_result(
        self,
        *,
        vector_degraded: bool = False,
        retrieval_sources: list[str] | None = None,
    ) -> eval_indexing.ChatResult:
        """构建最小聊天结果。"""
        retrieval_sources = retrieval_sources or ["fulltext", "vector"]
        return eval_indexing.ChatResult(
            answer="本轮索引验收标识是 FirstRAGIndexingEval-test。",
            sources=[
                {
                    "file_name": "eval.md",
                    "retrieval_sources": retrieval_sources,
                    "chunk_index": 0,
                },
            ],
            retrieval={
                "final_need_retrieval": True,
                "retrieved_count": 1,
                "source_count": 1,
                "diagnostics": {
                    "vector_degraded": vector_degraded,
                    "vector_errors": (
                        ["Chroma 单文件向量检索失败：file-id"]
                        if vector_degraded
                        else []
                    ),
                    "retrieval_sources": retrieval_sources,
                    "timing": {},
                    "llm": {},
                },
            },
            done={},
            elapsed_seconds=1.0,
        )

    def test_evaluate_result_requires_healthy_vector_source(self) -> None:
        """indexing eval 应在向量降级或 source 未走 vector 时失败。"""
        checks = eval_indexing.evaluate_result(
            upload_response={"success": True},
            file_record={"original_name": "eval.md", "status": "indexed"},
            job={"status": "succeeded"},
            chat_result=self.build_chat_result(
                vector_degraded=True,
                retrieval_sources=["fulltext"],
            ),
            expected_filename="eval.md",
            expected_keyword="FirstRAGIndexingEval-test",
        )
        results = {check["name"]: check for check in checks}

        self.assertFalse(results["chat_vector_not_degraded"]["passed"])
        self.assertFalse(results["uploaded_file_source_uses_vector"]["passed"])
        self.assertIn(
            "Chroma 单文件向量检索失败：file-id",
            results["chat_vector_not_degraded"]["actual"]["vector_errors"],
        )

    def test_write_report_includes_vector_errors(self) -> None:
        """Markdown 报告应展示向量降级错误摘要。"""
        chat_result = self.build_chat_result(vector_degraded=True)
        checks = eval_indexing.evaluate_result(
            upload_response={"success": True},
            file_record={"original_name": "eval.md", "status": "indexed"},
            job={"status": "succeeded", "id": "job-id"},
            chat_result=chat_result,
            expected_filename="eval.md",
            expected_keyword="FirstRAGIndexingEval-test",
        )
        run_record = eval_indexing.serialize_run_record(
            generated_at=datetime(2026, 7, 2, 9, 0, 0),
            base_url="http://127.0.0.1:8000",
            knowledge_base={"id": "kb-id", "name": "默认知识库"},
            filename="eval.md",
            file_id="file-id",
            job={"status": "succeeded", "id": "job-id"},
            chat_result=chat_result,
            checks=checks,
            cleanup_done=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            eval_indexing.write_report(report_path, run_record, None)
            report = report_path.read_text(encoding="utf-8")

        self.assertIn("- 向量降级：True", report)
        self.assertIn(
            "- 向量错误：['Chroma 单文件向量检索失败：file-id']",
            report,
        )

    def test_build_temp_file_supports_image_kind(self) -> None:
        """indexing eval 可生成小图片样例覆盖图片入库链路。"""
        filename, content, content_type, keyword = eval_indexing.build_temp_file(
            "run-id",
            "image",
        )

        self.assertTrue(filename.endswith(".png"))
        self.assertIn("FirstRAGImageIndexingEval-run-id", filename)
        self.assertEqual(content_type, "image/png")
        self.assertIsInstance(content, bytes)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IEND", content)
        self.assertEqual(keyword, "FirstRAGImageIndexingEval-run-id")


if __name__ == "__main__":
    unittest.main()
