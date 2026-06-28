#!/usr/bin/env bash
# Run the local release-readiness acceptance checks for FirstRAG.

set -euo pipefail

show_help() {
  cat <<'EOF'
Usage:
  scripts/acceptance_check.sh [--skip-real-eval] [--skip-frontend-tests] [--skip-frontend-build]

Environment variables:
  FIRSTRAG_CONDA_ENV              Conda env name. Default: firstrag
  FIRSTRAG_EVAL_USERNAME          Username for real backend evals.
  FIRSTRAG_EVAL_PASSWORD          Password for real backend evals.
  FIRSTRAG_EVAL_BASE_URL          Backend origin. Default: http://127.0.0.1:8000
  FIRSTRAG_SKIP_BACKEND_TESTS     Set to 1 to skip backend unittest.
  FIRSTRAG_SKIP_FRONTEND_LINT     Set to 1 to skip frontend lint.
  FIRSTRAG_SKIP_FRONTEND_TESTS    Set to 1 to skip frontend unit tests.
  FIRSTRAG_SKIP_FRONTEND_BUILD    Set to 1 to skip frontend build.
  FIRSTRAG_SKIP_REAL_EVAL         Set to 1 to skip RAG and indexing real evals.
  FIRSTRAG_SKIP_RAG_EVAL          Set to 1 to skip only RAG eval gate.
  FIRSTRAG_SKIP_INDEXING_EVAL     Set to 1 to skip only indexing eval.

Examples:
  scripts/acceptance_check.sh --skip-real-eval

  FIRSTRAG_EVAL_USERNAME=MonkeyBing \
  FIRSTRAG_EVAL_PASSWORD=123456 \
  scripts/acceptance_check.sh
EOF
}

log_step() {
  printf '\n==> %s\n' "$1"
}

require_eval_credentials() {
  if [[ -z "${FIRSTRAG_EVAL_USERNAME:-}" || -z "${FIRSTRAG_EVAL_PASSWORD:-}" ]]; then
    echo "Missing FIRSTRAG_EVAL_USERNAME or FIRSTRAG_EVAL_PASSWORD for real evals." >&2
    echo "Use --skip-real-eval for static checks only." >&2
    exit 2
  fi
}

SKIP_REAL_EVAL="${FIRSTRAG_SKIP_REAL_EVAL:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --skip-real-eval)
      SKIP_REAL_EVAL=1
      shift
      ;;
    --skip-frontend-build)
      FIRSTRAG_SKIP_FRONTEND_BUILD=1
      shift
      ;;
    --skip-frontend-tests)
      FIRSTRAG_SKIP_FRONTEND_TESTS=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Run scripts/acceptance_check.sh --help for usage." >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONDA_ENV="${FIRSTRAG_CONDA_ENV:-firstrag}"
BASE_URL="${FIRSTRAG_EVAL_BASE_URL:-http://127.0.0.1:8000}"

cd "${REPO_ROOT}"

if [[ "${FIRSTRAG_SKIP_BACKEND_TESTS:-0}" != "1" ]]; then
  log_step "Backend unittest"
  (
    cd backend
    conda run -n "${CONDA_ENV}" python -m unittest discover tests -v
  )
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_LINT:-0}" != "1" ]]; then
  log_step "Frontend lint"
  (
    cd frontend
    npm run lint
  )
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_TESTS:-0}" != "1" ]]; then
  log_step "Frontend unit tests"
  (
    cd frontend
    npm run test
  )
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  log_step "Frontend build"
  (
    cd frontend
    npm run build
  )
fi

if [[ "${SKIP_REAL_EVAL}" != "1" ]]; then
  require_eval_credentials

  if [[ "${FIRSTRAG_SKIP_RAG_EVAL:-0}" != "1" ]]; then
    log_step "RAG eval gate"
    FIRSTRAG_EVAL_BASE_URL="${BASE_URL}" "${SCRIPT_DIR}/rag_eval_gate.sh"
  fi

  if [[ "${FIRSTRAG_SKIP_INDEXING_EVAL:-0}" != "1" ]]; then
    log_step "Indexing eval"
    conda run -n "${CONDA_ENV}" python "${SCRIPT_DIR}/eval_indexing.py" \
      --base-url "${BASE_URL}"
  fi
fi

log_step "Acceptance checks passed"
