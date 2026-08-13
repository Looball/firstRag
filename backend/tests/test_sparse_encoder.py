"""Sparse encoder contract、runtime、service 与 client 回归测试。"""

from __future__ import annotations

import io
import json
import math
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.sparse_encoder_client import (
    SparseEncoderClient,
    SparseEncoderClientError,
)
from sparse_encoder.contract import (
    BGE_M3_MODEL_ID,
    BGE_M3_REVISION,
    EncodeRequest,
    EncodeResponse,
)
from sparse_encoder.runtime import (
    FixtureSparseRuntime,
    normalize_sparse_vectors,
)
from sparse_encoder.service import create_app
from sparse_encoder.settings import SparseEncoderSettings


class _FakeUrlResponse(io.BytesIO):
    """支持 context manager 的 urllib 测试响应。"""

    def __enter__(self) -> "_FakeUrlResponse":
        """返回当前 fake response。"""
        return self

    def __exit__(self, *args: object) -> None:
        """关闭 fake response。"""
        self.close()


def _fixture_settings(**overrides: object) -> SparseEncoderSettings:
    """创建边界较小的测试配置。"""
    values: dict[str, object] = {
        "runtime": "fixture",
        "max_batch_size": 2,
        "max_text_characters": 64,
        "max_request_bytes": 256,
        "request_timeout_seconds": 2.0,
    }
    values.update(overrides)
    return SparseEncoderSettings(**values).validate()


class SparseEncoderRuntimeTests(unittest.TestCase):
    """Sparse vectors 的稳定性和数值合法性测试。"""

    def test_fixture_is_stable_and_non_negative(self) -> None:
        """同一文本必须稳定输出有限、非负权重。"""
        runtime = FixtureSparseRuntime()
        runtime.load()

        first = runtime.encode(["企业内部 FirstRAG"], mode="query")
        second = runtime.encode(["企业内部 FirstRAG"], mode="query")

        self.assertEqual(first, second)
        self.assertTrue(first[0])
        self.assertTrue(all(index >= 0 for index in first[0]))
        self.assertTrue(
            all(math.isfinite(weight) and weight >= 0 for weight in first[0].values())
        )

    def test_normalize_sparse_vectors_rejects_invalid_values(self) -> None:
        """非法 index、NaN 和空向量不能进入 Milvus。"""
        with self.assertRaises(ValueError):
            normalize_sparse_vectors([{"-1": 1.0}])
        with self.assertRaises(ValueError):
            normalize_sparse_vectors([{"1": float("nan")}])
        with self.assertRaises(ValueError):
            normalize_sparse_vectors([{}])

    def test_contract_rejects_blank_text(self) -> None:
        """空白文本在进入 runtime 前失败。"""
        with self.assertRaises(ValueError):
            EncodeRequest(mode="document", texts=["   "])

    def test_settings_reject_non_cpu_runtime(self) -> None:
        """CPU-only image 不得接受无法兑现的 CUDA 配置。"""
        with self.assertRaisesRegex(ValueError, "仅支持 CPU"):
            SparseEncoderSettings(device="cuda").validate()

    def test_audit_requirement_matches_cpu_runtime_base_versions(self) -> None:
        """审计视图只能移除 torch 的 +cpu local version label。"""
        backend_root = Path(__file__).resolve().parents[1]
        runtime_lines = {
            line.strip()
            for line in (backend_root / "requirements-sparse-encoder.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith(("#", "--", "-r"))
        }
        audit_lines = {
            line.strip()
            for line in (backend_root / "requirements-sparse-encoder-audit.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith(("#", "--", "-r"))
        }

        normalized_runtime_lines = {
            line.replace("torch==2.13.0+cpu", "torch==2.13.0")
            for line in runtime_lines
        }
        self.assertEqual(
            normalized_runtime_lines,
            audit_lines,
        )


class SparseEncoderServiceTests(unittest.TestCase):
    """内部 HTTP service 的健康和资源门禁测试。"""

    @staticmethod
    def _wait_ready(client: TestClient) -> None:
        """等待后台 fixture load 完成。"""
        for _ in range(50):
            if client.get("/health/ready").status_code == 200:
                return
            time.sleep(0.01)
        raise AssertionError("fixture sparse encoder 未 ready")

    def test_health_and_encode_contract(self) -> None:
        """live/ready 分离且 query/document 都返回合法 vectors。"""
        app = create_app(_fixture_settings(), FixtureSparseRuntime())
        with TestClient(app) as client:
            self.assertEqual(client.get("/health/live").status_code, 200)
            self._wait_ready(client)
            query = client.post(
                "/v1/sparse/encode",
                json={"mode": "query", "texts": ["FirstRAG 企业检索"]},
            )
            document = client.post(
                "/v1/sparse/encode",
                json={"mode": "document", "texts": ["FirstRAG 企业检索"]},
            )

        self.assertEqual(query.status_code, 200)
        self.assertEqual(document.status_code, 200)
        self.assertEqual(query.json()["model"], BGE_M3_MODEL_ID)
        self.assertEqual(query.json()["revision"], BGE_M3_REVISION)
        self.assertTrue(query.json()["vectors"][0])

    def test_rejects_batch_text_and_body_limits(self) -> None:
        """batch、单文本和请求体超限分别明确失败。"""
        app = create_app(_fixture_settings(), FixtureSparseRuntime())
        with TestClient(app) as client:
            self._wait_ready(client)
            batch = client.post(
                "/v1/sparse/encode",
                json={"mode": "query", "texts": ["a", "b", "c"]},
            )
            long_text = client.post(
                "/v1/sparse/encode",
                json={"mode": "query", "texts": ["x" * 65]},
            )
            body = client.post(
                "/v1/sparse/encode",
                content=b"x" * 257,
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(batch.status_code, 422)
        self.assertEqual(long_text.status_code, 422)
        self.assertEqual(body.status_code, 413)


class SparseEncoderClientTests(unittest.TestCase):
    """Backend/worker 共享 client 的身份复核测试。"""

    def test_client_accepts_matching_identity(self) -> None:
        """匹配固定模型身份、模式和数量时返回 sparse vector。"""
        payload = EncodeResponse(
            model=BGE_M3_MODEL_ID,
            revision=BGE_M3_REVISION,
            mode="query",
            vectors=[{1: 0.5}],
        ).model_dump_json().encode("utf-8")
        with patch(
            "app.services.sparse_encoder_client.urlopen",
            return_value=_FakeUrlResponse(payload),
        ):
            vector = SparseEncoderClient().encode_query("企业知识")

        self.assertEqual(vector, {1: 0.5})

    def test_document_encoding_batches_large_child_sets(self) -> None:
        """document encoding 应按 client batch 拆分并保持原始顺序。"""
        observed_batches: list[list[str]] = []

        def respond(request, timeout):
            """按每批输入构造匹配 contract 的 fake response。"""
            del timeout
            request_payload = json.loads(request.data)
            texts = request_payload["texts"]
            observed_batches.append(texts)
            payload = EncodeResponse(
                model=BGE_M3_MODEL_ID,
                revision=BGE_M3_REVISION,
                mode="document",
                vectors=[{int(text): 1.0} for text in texts],
            ).model_dump_json().encode("utf-8")
            return _FakeUrlResponse(payload)

        with patch(
            "app.services.sparse_encoder_client.urlopen",
            side_effect=respond,
        ):
            vectors = SparseEncoderClient(batch_size=2).encode_documents([
                "0",
                "1",
                "2",
                "3",
                "4",
            ])

        self.assertEqual(observed_batches, [["0", "1"], ["2", "3"], ["4"]])
        self.assertEqual(vectors, [
            {0: 1.0},
            {1: 1.0},
            {2: 1.0},
            {3: 1.0},
            {4: 1.0},
        ])

    def test_client_rejects_revision_drift_without_leaking_text(self) -> None:
        """服务 revision 漂移时失败，异常不包含原始企业文本。"""
        payload = json.dumps(
            {
                "contract_version": 1,
                "model": BGE_M3_MODEL_ID,
                "revision": "wrong-revision",
                "mode": "document",
                "vectors": [{"1": 0.5}],
            }
        ).encode("utf-8")
        with patch(
            "app.services.sparse_encoder_client.urlopen",
            return_value=_FakeUrlResponse(payload),
        ):
            with self.assertRaises(SparseEncoderClientError) as context:
                SparseEncoderClient().encode_documents(["机密企业原文"])

        self.assertNotIn("机密企业原文", str(context.exception))
