"""BGE-M3 与 credential-free fixture sparse runtime。"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

from sparse_encoder.contract import EncodeMode
from sparse_encoder.settings import SparseEncoderSettings


_TOKEN_PATTERN = re.compile(r"[\w]+|[^\w\s]", re.UNICODE)
_FIXTURE_VOCABULARY_SIZE = 250_002


class SparseRuntime(Protocol):
    """Sparse inference runtime 需要实现的最小边界。"""

    def load(self) -> None:
        """加载模型并完成一次最小真实 inference。"""

    def encode(
        self,
        texts: list[str],
        *,
        mode: EncodeMode,
    ) -> list[dict[int, float]]:
        """把 document 或 query 编码为 sparse vectors。"""


def normalize_sparse_vectors(
    raw_vectors: object,
) -> list[dict[int, float]]:
    """将 FlagEmbedding lexical weights 规范为 Milvus sparse dict。"""
    if isinstance(raw_vectors, dict):
        candidates = [raw_vectors]
    elif isinstance(raw_vectors, list):
        candidates = raw_vectors
    else:
        raise ValueError("BGE-M3 未返回 lexical_weights 列表。")

    vectors: list[dict[int, float]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("BGE-M3 lexical_weights 元素必须是对象。")
        vector: dict[int, float] = {}
        for raw_index, raw_weight in candidate.items():
            index = int(raw_index)
            weight = float(raw_weight)
            if index < 0 or not math.isfinite(weight) or weight < 0:
                raise ValueError("BGE-M3 返回了非法 sparse index 或 weight。")
            if weight > 0:
                vector[index] = weight
        if not vector:
            raise ValueError("BGE-M3 返回了空 sparse vector。")
        vectors.append(vector)
    return vectors


class FixtureSparseRuntime:
    """CI 使用的确定性 sparse contract fixture，不代表模型质量。"""

    def __init__(self) -> None:
        """初始化未加载的 fixture runtime。"""
        self.loaded = False

    def load(self) -> None:
        """标记 fixture 已加载并执行最小输出检查。"""
        self.loaded = True
        self.encode(["FirstRAG sparse probe"], mode="query")

    @staticmethod
    def _token_index(token: str) -> int:
        """把 token 稳定映射到测试 vocabulary，保留 0 作为空位。"""
        digest = hashlib.blake2b(
            token.encode("utf-8"),
            digest_size=8,
            person=b"firstrag",
        ).digest()
        return int.from_bytes(digest, "big") % (_FIXTURE_VOCABULARY_SIZE - 1) + 1

    def encode(
        self,
        texts: list[str],
        *,
        mode: EncodeMode,
    ) -> list[dict[int, float]]:
        """按稳定 token hash 生成非负 sparse vectors。"""
        if not self.loaded:
            raise RuntimeError("fixture sparse runtime 尚未加载。")
        if mode not in {"document", "query"}:
            raise ValueError("mode 必须是 document 或 query。")
        vectors: list[dict[int, float]] = []
        for text in texts:
            tokens = [token.casefold() for token in _TOKEN_PATTERN.findall(text)]
            counts = Counter(tokens)
            vector: dict[int, float] = {}
            for token, count in counts.items():
                index = self._token_index(token)
                vector[index] = vector.get(index, 0.0) + 1.0 + math.log1p(count)
            if not vector:
                raise ValueError("文本没有可编码 token。")
            vectors.append(dict(sorted(vector.items())))
        return vectors


class BgeM3SparseRuntime:
    """固定 revision 的本地 BGE-M3 learned sparse runtime。"""

    def __init__(self, settings: SparseEncoderSettings) -> None:
        """保存模型配置，模型只在 load 时加载一次。"""
        self.settings = settings
        self._model: object | None = None

    def load(self) -> None:
        """下载或读取固定 snapshot，加载模型并完成最小 sparse inference。"""
        from FlagEmbedding import BGEM3FlagModel
        from huggingface_hub import snapshot_download

        snapshot_path = snapshot_download(
            repo_id=self.settings.model_id,
            revision=self.settings.revision,
            cache_dir=self.settings.cache_dir,
            local_files_only=self.settings.offline,
        )
        self._model = BGEM3FlagModel(
            snapshot_path,
            devices=self.settings.device,
            use_fp16=self.settings.use_fp16,
            batch_size=self.settings.batch_size,
            query_max_length=self.settings.max_length,
            passage_max_length=self.settings.max_length,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
            trust_remote_code=False,
        )
        self.encode(["FirstRAG sparse probe"], mode="query")

    def encode(
        self,
        texts: list[str],
        *,
        mode: EncodeMode,
    ) -> list[dict[int, float]]:
        """调用 query/corpus 专用入口并只返回 lexical weights。"""
        if self._model is None:
            raise RuntimeError("BGE-M3 sparse runtime 尚未加载。")
        encode_method = (
            getattr(self._model, "encode_queries")
            if mode == "query"
            else getattr(self._model, "encode_corpus")
        )
        result = encode_method(
            texts,
            batch_size=self.settings.batch_size,
            max_length=self.settings.max_length,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        if not isinstance(result, dict):
            raise ValueError("BGE-M3 encode 响应必须是对象。")
        return normalize_sparse_vectors(result.get("lexical_weights"))


def create_runtime(settings: SparseEncoderSettings) -> SparseRuntime:
    """按显式 mode 创建 real 或 CI fixture runtime。"""
    if settings.runtime == "fixture":
        return FixtureSparseRuntime()
    return BgeM3SparseRuntime(settings)
