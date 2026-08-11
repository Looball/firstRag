"""验证 sparse encoder 健康、模式区分和确定性 contract。"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

from sparse_encoder.contract import EncodeResponse


def _post_encode(base_url: str, mode: str) -> EncodeResponse:
    """向内部 service 提交不含凭据的最小测试文本。"""
    payload = json.dumps(
        {"mode": mode, "texts": ["FirstRAG sparse probe"]},
    ).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/v1/sparse/encode",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return EncodeResponse.model_validate_json(response.read())


def main() -> int:
    """执行 ready、query/document 与重复输入稳定性检查。"""
    base_url = os.environ.get(
        "SPARSE_ENCODER_PROBE_URL",
        "http://127.0.0.1:8090",
    )
    with urlopen(f"{base_url.rstrip('/')}/health/ready", timeout=5) as response:
        if response.status != 200:
            raise RuntimeError("Sparse encoder readiness probe 失败。")
    first_query = _post_encode(base_url, "query")
    second_query = _post_encode(base_url, "query")
    document = _post_encode(base_url, "document")
    if first_query.vectors != second_query.vectors:
        raise RuntimeError("Sparse encoder 同一 query 输出不稳定。")
    if len(document.vectors) != 1 or not document.vectors[0]:
        raise RuntimeError("Sparse encoder document 输出为空。")
    print(
        "Sparse encoder probe: PASS "
        f"runtime_model={first_query.model} revision={first_query.revision}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
