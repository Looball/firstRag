#!/usr/bin/env bash
# Run the project-standard RAG regression eval with quality gates.

set -euo pipefail

show_help() {
  cat <<'EOF'
Usage:
  FIRSTRAG_EVAL_USERNAME=用户名 FIRSTRAG_EVAL_PASSWORD=密码 scripts/rag_eval_gate.sh [extra eval_rag.py args]

Environment variables:
  FIRSTRAG_CONDA_ENV                              Conda env name. Default: firstrag
  FIRSTRAG_EVAL_BASE_URL                         Backend origin. Default: http://127.0.0.1:8000
  FIRSTRAG_EVAL_TIMEOUT                          HTTP timeout seconds. Default: 240
  FIRSTRAG_EVAL_MIN_PASS_RATE                    Minimum pass rate. Default: 1.0
  FIRSTRAG_EVAL_MIN_AVERAGE_SOURCES              Minimum average source count. Default: 1
  FIRSTRAG_EVAL_MAX_AVERAGE_FIRST_TOKEN_MS       Maximum average first-token wait. Default: 10000
  FIRSTRAG_EVAL_MAX_AVERAGE_ELAPSED_SECONDS      Maximum average case latency. Default: 30
  FIRSTRAG_EVAL_CASES                            Optional cases JSONL path.
  FIRSTRAG_EVAL_REPORT                           Optional markdown report path.
  FIRSTRAG_EVAL_RUNS_DIR                         Optional JSON history directory.
  FIRSTRAG_EVAL_KNOWLEDGE_BASE_NAME              Optional knowledge base name override.
  FIRSTRAG_EVAL_NO_HISTORY                       Set to 1 to skip timestamped JSON history.

Examples:
  FIRSTRAG_EVAL_USERNAME=MonkeyBing FIRSTRAG_EVAL_PASSWORD=123456 scripts/rag_eval_gate.sh

  FIRSTRAG_EVAL_USERNAME=MonkeyBing FIRSTRAG_EVAL_PASSWORD=123456 \
  FIRSTRAG_EVAL_MAX_AVERAGE_FIRST_TOKEN_MS=15000 \
  scripts/rag_eval_gate.sh --knowledge-base-name 默认知识库
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  show_help
  exit 0
fi

if [[ -z "${FIRSTRAG_EVAL_USERNAME:-}" || -z "${FIRSTRAG_EVAL_PASSWORD:-}" ]]; then
  echo "Missing FIRSTRAG_EVAL_USERNAME or FIRSTRAG_EVAL_PASSWORD." >&2
  echo "Run scripts/rag_eval_gate.sh --help for usage." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONDA_ENV="${FIRSTRAG_CONDA_ENV:-firstrag}"
BASE_URL="${FIRSTRAG_EVAL_BASE_URL:-http://127.0.0.1:8000}"
TIMEOUT="${FIRSTRAG_EVAL_TIMEOUT:-240}"
MIN_PASS_RATE="${FIRSTRAG_EVAL_MIN_PASS_RATE:-1.0}"
MIN_AVERAGE_SOURCES="${FIRSTRAG_EVAL_MIN_AVERAGE_SOURCES:-1}"
MAX_AVERAGE_FIRST_TOKEN_MS="${FIRSTRAG_EVAL_MAX_AVERAGE_FIRST_TOKEN_MS:-10000}"
MAX_AVERAGE_ELAPSED_SECONDS="${FIRSTRAG_EVAL_MAX_AVERAGE_ELAPSED_SECONDS:-30}"

cmd=(
  conda run -n "${CONDA_ENV}" python "${REPO_ROOT}/scripts/eval_rag.py"
  --base-url "${BASE_URL}"
  --timeout "${TIMEOUT}"
  --min-pass-rate "${MIN_PASS_RATE}"
  --min-average-sources "${MIN_AVERAGE_SOURCES}"
  --max-average-first-token-ms "${MAX_AVERAGE_FIRST_TOKEN_MS}"
  --max-average-elapsed-seconds "${MAX_AVERAGE_ELAPSED_SECONDS}"
)

if [[ -n "${FIRSTRAG_EVAL_CASES:-}" ]]; then
  cmd+=(--cases "${FIRSTRAG_EVAL_CASES}")
fi

if [[ -n "${FIRSTRAG_EVAL_REPORT:-}" ]]; then
  cmd+=(--report "${FIRSTRAG_EVAL_REPORT}")
fi

if [[ -n "${FIRSTRAG_EVAL_RUNS_DIR:-}" ]]; then
  cmd+=(--runs-dir "${FIRSTRAG_EVAL_RUNS_DIR}")
fi

if [[ -n "${FIRSTRAG_EVAL_KNOWLEDGE_BASE_NAME:-}" ]]; then
  cmd+=(--knowledge-base-name "${FIRSTRAG_EVAL_KNOWLEDGE_BASE_NAME}")
fi

if [[ "${FIRSTRAG_EVAL_NO_HISTORY:-}" == "1" ]]; then
  cmd+=(--no-history)
fi

exec "${cmd[@]}" "$@"
