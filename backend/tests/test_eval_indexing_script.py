import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pymupdf


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_indexing
from scripts import full_stack_e2e_provider


class EvalIndexingScriptTests(unittest.TestCase):
    """上传与向量化验收脚本测试。"""

    def test_provider_stub_echoes_indexing_marker(self) -> None:
        """隔离 provider 应回答每轮随机 marker，而非固定假阳性。"""
        request = full_stack_e2e_provider.ChatCompletionRequest(
            model="firstrag-e2e-model",
            messages=[{
                "role": "user",
                "content": "请回答 FirstRAGIndexingEval-20260809-abcd1234",
            }],
        )
        self.assertEqual(
            full_stack_e2e_provider._answer_for_request(request),
            "FirstRAG 索引验收标识是 "
            "FirstRAGIndexingEval-20260809-abcd1234。",
        )

    def build_chat_result(
        self,
        *,
        vector_degraded: bool = False,
        retrieval_sources: list[str] | None = None,
        filename: str = "eval.md",
        page_number: int | None = None,
        pdf_parse_method: str | None = None,
    ) -> eval_indexing.ChatResult:
        """构建最小聊天结果。"""
        retrieval_sources = retrieval_sources or ["fulltext", "vector"]
        return eval_indexing.ChatResult(
            answer="本轮索引验收标识是 FirstRAGIndexingEval-test。",
            sources=[
                {
                    "file_name": filename,
                    "retrieval_sources": retrieval_sources,
                    "chunk_index": 0,
                    "page_number": page_number,
                    "pdf_parse_method": pdf_parse_method,
                },
            ],
            retrieval={
                "final_need_retrieval": True,
                "retrieved_count": 1,
                "source_count": 1,
                "diagnostics": {
                    "vector_degraded": vector_degraded,
                    "vector_errors": (
                        ["Milvus 单文件向量检索失败：file-id"]
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

    def build_page_preview_evidence(
        self,
        run_id: str = "run-id",
        page_number: int = 2,
    ) -> eval_indexing.PdfPagePreviewEvidence:
        """从 mixed PDF 指定页生成与真实接口等价的预览证据。"""
        _, pdf_content, _, _ = eval_indexing.build_temp_mixed_pdf_file(run_id)
        document = pymupdf.open(stream=pdf_content, filetype="pdf")
        try:
            page = document.load_page(page_number - 1)
            preview_content = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2),
                colorspace=pymupdf.csRGB,
                alpha=False,
            ).tobytes("png")
        finally:
            document.close()
        return eval_indexing.inspect_pdf_page_preview(
            preview_content=preview_content,
            response_headers={
                "content-type": "image/png",
                "cache-control": "private, max-age=60",
                "content-disposition": (
                    f'inline; filename="page-{page_number}.png"'
                ),
            },
            pdf_content=pdf_content,
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
            "Milvus 单文件向量检索失败：file-id",
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
        self.assertEqual(run_record["schema_version"], 3)
        self.assertEqual(run_record["file"]["kind"], "markdown")
        self.assertIsNone(run_record["source_context"])
        self.assertIsNone(run_record["page_preview"])

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            eval_indexing.write_report(report_path, run_record, None)
            report = report_path.read_text(encoding="utf-8")

        self.assertIn("- 向量降级：True", report)
        self.assertIn(
            "- 向量错误：['Milvus 单文件向量检索失败：file-id']",
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

    def test_build_temp_file_supports_mixed_pdf_kind(self) -> None:
        """mixed PDF 应保持 native、scan、native 三页文本层边界。"""
        filename, content, content_type, keyword = eval_indexing.build_temp_file(
            "run-id",
            "mixed-pdf",
        )

        self.assertTrue(filename.endswith(".pdf"))
        self.assertEqual(content_type, "application/pdf")
        self.assertIsInstance(content, bytes)
        document = pymupdf.open(stream=content, filetype="pdf")
        try:
            self.assertEqual(document.page_count, 3)
            page_texts = [
                document.load_page(page_index).get_text().strip()
                for page_index in range(document.page_count)
            ]
            self.assertIn("T083 NATIVE START ID", page_texts[0])
            self.assertEqual(page_texts[1], "")
            self.assertEqual(len(document.load_page(1).get_images()), 1)
            self.assertIn("T083 NATIVE END ID", page_texts[2])
        finally:
            document.close()
        self.assertEqual(keyword, "T083 SCAN CODE ID")

    def test_mixed_pdf_result_requires_page_two_ocr_source_and_context(self) -> None:
        """mixed PDF 必须在 source 和原文上下文中保持页码及解析方式。"""
        filename = "eval.pdf"
        chat_result = self.build_chat_result(
            filename=filename,
            page_number=2,
            pdf_parse_method="ocr",
        )
        chat_result.answer = "T083 SCAN CODE ID"
        source_context = {
            "target_chunk_index": 1,
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "T083 NATIVE START ID",
                    "location": {
                        "page_number": 1,
                        "pdf_parse_method": "native_text",
                    },
                    "is_target": False,
                },
                {
                    "chunk_index": 1,
                    "content": "T083 SCAN CODE ID",
                    "location": {
                        "page_number": 2,
                        "pdf_parse_method": "ocr",
                    },
                    "is_target": True,
                },
                {
                    "chunk_index": 2,
                    "content": "T083 NATIVE END ID",
                    "location": {
                        "page_number": 3,
                        "pdf_parse_method": "native_text",
                    },
                    "is_target": False,
                },
            ],
        }

        checks = eval_indexing.evaluate_result(
            upload_response={"success": True},
            file_record={"original_name": filename, "status": "indexed"},
            job={"status": "succeeded"},
            chat_result=chat_result,
            expected_filename=filename,
            expected_keyword="T083 SCAN CODE ID",
            file_kind="mixed-pdf",
            source_context=source_context,
            mixed_pdf_keywords=eval_indexing.build_mixed_pdf_keywords("run-id"),
            page_preview=self.build_page_preview_evidence(),
        )
        results = {check["name"]: check["passed"] for check in checks}

        self.assertTrue(all(results.values()))
        self.assertTrue(results["mixed_pdf_source_points_to_scanned_page"])
        self.assertTrue(results["mixed_pdf_context_preserves_page_order"])
        self.assertTrue(results["mixed_pdf_page_preview_is_private_png"])
        self.assertTrue(results["mixed_pdf_page_preview_matches_page_2"])

    def test_mixed_pdf_result_rejects_native_source_for_scan_target(self) -> None:
        """扫描标识若引用到 native 页，端到端门禁必须失败。"""
        filename = "eval.pdf"
        chat_result = self.build_chat_result(
            filename=filename,
            page_number=1,
            pdf_parse_method="native_text",
        )
        checks = eval_indexing.evaluate_result(
            upload_response={"success": True},
            file_record={"original_name": filename, "status": "indexed"},
            job={"status": "succeeded"},
            chat_result=chat_result,
            expected_filename=filename,
            expected_keyword="T083 SCAN CODE ID",
            file_kind="mixed-pdf",
            source_context=None,
            mixed_pdf_keywords=eval_indexing.build_mixed_pdf_keywords("run-id"),
        )
        results = {check["name"]: check["passed"] for check in checks}

        self.assertFalse(results["mixed_pdf_source_points_to_scanned_page"])
        self.assertFalse(results["mixed_pdf_context_has_ocr_page_2"])

    def test_pdf_page_preview_evidence_identifies_the_rendered_page(self) -> None:
        """图像门禁应按像素内容识别预览页，而非只相信请求路径。"""
        evidence = self.build_page_preview_evidence(page_number=2)

        self.assertEqual(evidence.closest_page_number, 2)
        self.assertEqual((evidence.width, evidence.height), (1190, 1684))
        self.assertEqual(evidence.page_mean_differences[2], 0)
        self.assertGreater(evidence.page_mean_differences[1], 0.002)
        self.assertGreater(evidence.page_mean_differences[3], 0.002)

    def test_mixed_pdf_result_rejects_wrong_page_preview(self) -> None:
        """接口若误返回第 1 页，mixed PDF 门禁必须明确失败。"""
        checks = eval_indexing.evaluate_mixed_pdf_result(
            chat_result=self.build_chat_result(
                filename="eval.pdf",
                page_number=2,
                pdf_parse_method="ocr",
            ),
            source_context=None,
            expected_filename="eval.pdf",
            expected_keywords=eval_indexing.build_mixed_pdf_keywords("run-id"),
            page_preview=self.build_page_preview_evidence(page_number=1),
        )
        results = {check["name"]: check["passed"] for check in checks}

        self.assertFalse(results["mixed_pdf_page_preview_matches_page_2"])


if __name__ == "__main__":
    unittest.main()
