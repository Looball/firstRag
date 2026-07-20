#!/usr/bin/env bash
# Run the local release-readiness acceptance checks for FirstRAG.

set -Eeuo pipefail

CURRENT_STEP=""

on_error() {
  local exit_code=$?
  if [[ -n "${CURRENT_STEP}" ]]; then
    echo "[fail] ${CURRENT_STEP} failed with exit code ${exit_code}" >&2
  else
    echo "Acceptance check failed with exit code ${exit_code}" >&2
  fi
  exit "${exit_code}"
}

trap on_error ERR

show_help() {
  cat <<'EOF'
Usage:
  scripts/acceptance_check.sh [--skip-real-eval] [--skip-infrastructure-check] [--skip-migration-check] [--skip-frontend-tests] [--skip-frontend-build]

Environment variables:
  FIRSTRAG_CONDA_ENV              Conda env name. Default: firstrag
  FIRSTRAG_EVAL_USERNAME          Username for real backend evals.
  FIRSTRAG_EVAL_PASSWORD          Password for real backend evals.
  FIRSTRAG_EVAL_BASE_URL          Backend origin. Default: http://127.0.0.1:8000
  FIRSTRAG_SKIP_MIGRATION_CHECK   Set to 1 to skip migration file/dry-run checks.
  FIRSTRAG_REQUIRE_MIGRATION_DRY_RUN
                                  Set to 1 to fail when DATABASE_URL is unavailable.
  DATABASE_URL                    Database URL used by migration dry-run.
  COMPOSE_DATABASE_URL            Compose database URL fallback for migration dry-run.
  FIRSTRAG_PREFLIGHT_ENV_FILE     Env file used by infrastructure preflight. Default: .env
  FIRSTRAG_SKIP_INFRASTRUCTURE_CHECK
                                  Set to 1 only for static checks without Docker services.
  FIRSTRAG_SKIP_BACKEND_COMPILE   Set to 1 to skip backend compileall.
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

run_step() {
  local name="$1"
  shift
  log_step "$name"
  CURRENT_STEP="$name"
  "$@"
  CURRENT_STEP=""
  printf '[pass] %s passed\n' "$name"
}

require_eval_credentials() {
  if [[ -z "${FIRSTRAG_EVAL_USERNAME:-}" || -z "${FIRSTRAG_EVAL_PASSWORD:-}" ]]; then
    echo "Missing FIRSTRAG_EVAL_USERNAME or FIRSTRAG_EVAL_PASSWORD for real evals." >&2
    echo "Use --skip-real-eval for static checks only." >&2
    exit 2
  fi
}

run_migration_check() {
  conda run -n "${CONDA_ENV}" python "${SCRIPT_DIR}/migrate_db.py" --list

  if [[ -n "${DATABASE_URL:-}" || -n "${COMPOSE_DATABASE_URL:-}" ]]; then
    conda run -n "${CONDA_ENV}" python "${SCRIPT_DIR}/migrate_db.py" --dry-run
    return
  fi

  if [[ "${FIRSTRAG_REQUIRE_MIGRATION_DRY_RUN:-0}" == "1" ]]; then
    echo "Migration dry-run requires DATABASE_URL or COMPOSE_DATABASE_URL." >&2
    return 2
  fi

  echo "Skipping migration dry-run because DATABASE_URL/COMPOSE_DATABASE_URL is not set."
  echo "Set FIRSTRAG_REQUIRE_MIGRATION_DRY_RUN=1 to require database dry-run."
}

run_infrastructure_preflight() {
  conda run -n "${CONDA_ENV}" python "${SCRIPT_DIR}/production_preflight.py" \
    --env-file "${PREFLIGHT_ENV_FILE}" \
    --migration-method compose \
    --skip-migration-dry-run \
    --check-runtime-health
}

run_backend_compileall() {
  (
    cd "${REPO_ROOT}/backend"
    conda run -n "${CONDA_ENV}" python -m compileall app
  )
}

run_backend_unittest() {
  (
    cd "${REPO_ROOT}/backend"
    conda run -n "${CONDA_ENV}" python -m unittest discover tests -v
  )
}

run_frontend_lint() {
  (
    cd "${REPO_ROOT}/frontend"
    npm run lint
  )
}

run_frontend_tests() {
  (
    cd "${REPO_ROOT}/frontend"
    npm run test
  )
}

run_frontend_build() {
  (
    cd "${REPO_ROOT}/frontend"
    npm run build
  )
}

run_rag_eval_gate() {
  FIRSTRAG_EVAL_BASE_URL="${BASE_URL}" "${SCRIPT_DIR}/rag_eval_gate.sh"
}

run_indexing_eval() {
  conda run -n "${CONDA_ENV}" python "${SCRIPT_DIR}/eval_indexing.py" \
    --base-url "${BASE_URL}"
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
    --skip-migration-check)
      FIRSTRAG_SKIP_MIGRATION_CHECK=1
      shift
      ;;
    --skip-infrastructure-check)
      FIRSTRAG_SKIP_INFRASTRUCTURE_CHECK=1
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
PREFLIGHT_ENV_FILE="${FIRSTRAG_PREFLIGHT_ENV_FILE:-${REPO_ROOT}/.env}"

cd "${REPO_ROOT}"

if [[ "${FIRSTRAG_SKIP_INFRASTRUCTURE_CHECK:-0}" != "1" ]]; then
  run_step "Infrastructure preflight" run_infrastructure_preflight
fi

if [[ "${FIRSTRAG_SKIP_MIGRATION_CHECK:-0}" != "1" ]]; then
  run_step "Migration check" run_migration_check
fi

if [[ "${FIRSTRAG_SKIP_BACKEND_COMPILE:-0}" != "1" ]]; then
  run_step "Backend compileall" run_backend_compileall
fi

if [[ "${FIRSTRAG_SKIP_BACKEND_TESTS:-0}" != "1" ]]; then
  run_step "Backend unittest" run_backend_unittest
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_LINT:-0}" != "1" ]]; then
  run_step "Frontend lint" run_frontend_lint
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_TESTS:-0}" != "1" ]]; then
  run_step "Frontend unit tests" run_frontend_tests
fi

if [[ "${FIRSTRAG_SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  run_step "Frontend build" run_frontend_build
fi

if [[ "${SKIP_REAL_EVAL}" != "1" ]]; then
  require_eval_credentials

  if [[ "${FIRSTRAG_SKIP_RAG_EVAL:-0}" != "1" ]]; then
    run_step "RAG eval gate" run_rag_eval_gate
  fi

  if [[ "${FIRSTRAG_SKIP_INDEXING_EVAL:-0}" != "1" ]]; then
    run_step "Indexing eval" run_indexing_eval
  fi
fi

log_step "Acceptance checks passed"
