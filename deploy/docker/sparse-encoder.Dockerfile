FROM python:3.12-slim AS fixture

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV"

COPY backend/requirements-sparse-encoder-api.txt /app/backend/requirements-sparse-encoder-api.txt
RUN pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -r /app/backend/requirements-sparse-encoder-api.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/sparse_encoder /app/sparse_encoder

RUN groupadd --gid 10001 firstrag \
    && useradd --uid 10001 --gid 10001 --no-create-home firstrag \
    && mkdir -p /models/huggingface/xet \
    && chown -R firstrag:firstrag /app /models/huggingface

USER 10001:10001

EXPOSE 8090

CMD ["python", "-m", "uvicorn", "sparse_encoder.main:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1"]


FROM fixture AS runtime

USER root

COPY backend/requirements-sparse-encoder.txt /app/backend/requirements-sparse-encoder.txt
RUN set -eux; \
    pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple; \
    pip install -r /app/backend/requirements-sparse-encoder.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; \
    pip check; \
    python -c "import torch, transformers; from FlagEmbedding import BGEM3FlagModel"; \
    pip uninstall -y pip setuptools wheel; \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true

USER 10001:10001
