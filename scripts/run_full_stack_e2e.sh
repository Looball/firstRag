#!/usr/bin/env bash
# Run the isolated, credential-free FirstRAG full-stack browser gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_NAME="${FIRSTRAG_E2E_PROJECT_NAME:-firstrag-t089-$$}"
E2E_BACKEND_PORT="${FIRSTRAG_E2E_BACKEND_PORT:-18080}"
E2E_FRONTEND_PORT="${FIRSTRAG_E2E_FRONTEND_PORT:-13000}"
E2E_POSTGRES_PORT="${FIRSTRAG_E2E_POSTGRES_PORT:-25432}"
USERNAME="${FIRSTRAG_E2E_USERNAME:-firstrag_e2e_$$}"
PASSWORD="${FIRSTRAG_E2E_PASSWORD:-E2eOnly-123456}"
PAUSE_AFTER_TEST="${FIRSTRAG_E2E_PAUSE_AFTER_TEST:-0}"
COMPOSE_ARGS=(
  --env-file /dev/null
  --profile milvus
  -f "${REPO_ROOT}/docker-compose.yml"
  -f "${REPO_ROOT}/deploy/docker/docker-compose.e2e.yml"
)

if [[ ! "${PROJECT_NAME}" =~ ^firstrag-t089-[a-zA-Z0-9_-]+$ ]]; then
  echo "FIRSTRAG_E2E_PROJECT_NAME must start with firstrag-t089-." >&2
  exit 2
fi
if [[ "${PAUSE_AFTER_TEST}" != "0" && "${PAUSE_AFTER_TEST}" != "1" ]]; then
  echo "FIRSTRAG_E2E_PAUSE_AFTER_TEST must be 0 or 1." >&2
  exit 2
fi
if [[ "${PAUSE_AFTER_TEST}" == "1" && ! -t 0 ]]; then
  echo "FIRSTRAG_E2E_PAUSE_AFTER_TEST=1 requires an interactive terminal." >&2
  exit 2
fi

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
export FIRSTRAG_E2E_BACKEND_PORT="${E2E_BACKEND_PORT}"
export FIRSTRAG_E2E_FRONTEND_PORT="${E2E_FRONTEND_PORT}"
export FIRSTRAG_E2E_POSTGRES_PORT="${E2E_POSTGRES_PORT}"
export BACKEND_PORT="127.0.0.1:${E2E_BACKEND_PORT}"
export FRONTEND_PORT="127.0.0.1:${E2E_FRONTEND_PORT}"
export POSTGRES_PORT="127.0.0.1:${E2E_POSTGRES_PORT}"

cleanup() {
  status=$?
  if [[ "${status}" -ne 0 ]]; then
    mkdir -p "${REPO_ROOT}/tmp/full-stack-e2e"
    docker compose "${COMPOSE_ARGS[@]}" logs --no-color \
      >"${REPO_ROOT}/tmp/full-stack-e2e/docker-compose.log" 2>&1 || true
  fi
  docker compose "${COMPOSE_ARGS[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

cd "${REPO_ROOT}"
docker compose "${COMPOSE_ARGS[@]}" up -d --build

ready=0
for _ in $(seq 1 90); do
  if curl --fail --silent "http://127.0.0.1:${E2E_BACKEND_PORT}/health" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:${E2E_FRONTEND_PORT}/login" >/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "${ready}" -ne 1 ]]; then
  echo "Full-stack E2E services did not become ready." >&2
  exit 1
fi

curl --fail --silent --show-error \
  --request POST \
  --header "Content-Type: application/json" \
  --data "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}" \
  "http://127.0.0.1:${E2E_BACKEND_PORT}/register" >/dev/null

docker compose "${COMPOSE_ARGS[@]}" exec -T backend \
  python /app/e2e-scripts/seed_full_stack_e2e.py \
  --username "${USERNAME}"

cd "${REPO_ROOT}/frontend"
FIRSTRAG_E2E_BASE_URL="http://127.0.0.1:${E2E_FRONTEND_PORT}" \
FIRSTRAG_E2E_USERNAME="${USERNAME}" \
FIRSTRAG_E2E_PASSWORD="${PASSWORD}" \
npx --no-install playwright test \
  --config playwright.full-stack.config.ts

if [[ "${PAUSE_AFTER_TEST}" == "1" ]]; then
  printf '\n%s\n' "Credential-free tutorial verification passed."
  printf '%s\n' \
    "Compose project: ${PROJECT_NAME}" \
    "Open: http://127.0.0.1:${E2E_FRONTEND_PORT}/login" \
    "Temporary username: ${USERNAME}" \
    "Temporary password: ${PASSWORD}" \
    "Uploaded file: t089-full-stack-source.txt" \
    "Question: 请返回资料中的验收标识 T089 FULL STACK SOURCE" \
    "Expected answer: FirstRAG 全栈验收标识是 T089 FULL STACK SOURCE。" \
    "Press Enter to remove this project's containers, network, and volumes."
  read -r _ || true
fi
