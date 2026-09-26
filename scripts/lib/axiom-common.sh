# shellcheck shell=bash
# Shared helpers for ./axiom (sourced, not executed).
: "${REPO_ROOT:?REPO_ROOT must be set before sourcing axiom-common.sh}"

readonly GRACE_PG_HOST_PORT=5433
# Local docker-compose Postgres (axiom DB). Use when spawning the agent worker so it never follows
# TEST_DATABASE_URL / axiom_test from pytest or a stale shell export.
readonly GRACE_DEV_DATABASE_URL="postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:${GRACE_PG_HOST_PORT}/axiom"
readonly GRACE_REDIS_HOST_PORT=6380
readonly GRACE_BACKEND_PORT=8000
readonly GRACE_GATEWAY_PORT=8001
readonly GRACE_FRONTEND_PORT=3000

readonly GRACE_DIR="${REPO_ROOT}/.axiom"
readonly GRACE_LOG="${GRACE_DIR}/last-session.log"
readonly GRACE_LOG_PREV="${GRACE_DIR}/prev-session.log"
readonly GRACE_PID_BACKEND="${GRACE_DIR}/backend.pid"
readonly GRACE_PID_GATEWAY="${GRACE_DIR}/gateway.pid"
readonly GRACE_PID_FRONTEND="${GRACE_DIR}/frontend.pid"
readonly GRACE_PID_WORKER="${GRACE_DIR}/worker.pid"

GRACE_SHUTTING_DOWN=0

# shellcheck source=axiom-ports.sh
source "${REPO_ROOT}/scripts/lib/axiom-ports.sh"

require_docker_group() {
  [[ "$(uname -s)" == "Darwin" ]] && return 0
  if ! groups | grep -qw docker; then
    cat <<'EOF' >&2
✗ Your user is not in the docker group.
  Run this once, then log out and back in (or newgrp docker):
    sudo usermod -aG docker $USER && newgrp docker
  More: docs/dev-setup.md
EOF
    exit 1
  fi
}

axiom_compose() {
  (cd "${REPO_ROOT}" && docker compose "$@")
}

_ansi() {
  if [[ -n "${NO_COLOR:-}" ]] || ! [[ -t 1 ]]; then
    echo ""
    return
  fi
  case "$1" in
    green) echo $'\033[32m' ;;
    red) echo $'\033[31m' ;;
    cyan) echo $'\033[36m' ;;
    blue) echo $'\033[34m' ;;
    magenta) echo $'\033[35m' ;;
    reset) echo $'\033[0m' ;;
    *) echo "" ;;
  esac
}

axiom_log_tagged() {
  local tag=$1
  local color_name=$2
  local msg=$3
  local ts
  ts="$(date '+%H:%M:%S')"
  local plain="[${ts}] [${tag}] ${msg}"
  echo "${plain}" >>"${GRACE_LOG}"
  if [[ -n "${NO_COLOR:-}" ]] || ! [[ -t 1 ]]; then
    echo "${plain}"
  else
    local c r
    c="$(_ansi "${color_name}")"
    r="$(_ansi reset)"
    echo "${c}[${ts}] [${tag}]${r} ${msg}"
  fi
}

ensure_axiom_dir() {
  mkdir -p "${GRACE_DIR}"
  if [[ -f "${GRACE_LOG}" ]]; then
    mv -f "${GRACE_LOG}" "${GRACE_LOG_PREV}" 2>/dev/null || true
  fi
  : >"${GRACE_LOG}"
}

wait_for_http() {
  local url=$1
  local timeout=$2
  local label=$3
  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "${url}" 2>/dev/null || echo 000)"
    if [[ "${code}" =~ ^2 ]] || [[ "${code}" =~ ^3 ]]; then
      return 0
    fi
    sleep 1
  done
  echo "axiom: timeout waiting for ${label} (${url})" >&2
  return 1
}

wait_postgres_healthy() {
  local timeout=$1
  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    local st
    st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' axiom-postgres 2>/dev/null || echo missing)"
    if [[ "${st}" == healthy ]]; then
      return 0
    fi
    sleep 1
  done
  echo "axiom: timeout waiting for postgres container healthy" >&2
  return 1
}

wait_redis_pong() {
  local timeout=$1
  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    if axiom_compose exec -T redis redis-cli PING 2>/dev/null | grep -qx PONG; then
      return 0
    fi
    sleep 1
  done
  echo "axiom: timeout waiting for redis PING" >&2
  return 1
}

axiom_run_help() {
  cat <<'EOF'
AXIOM local development CLI

Usage: axiom <command>

Commands:
  dev      Start Postgres, Redis, migrations, backend, gateway, frontend, agent worker
           (foreground; Ctrl+C stops all). Use --no-start to stop after DB + automint (no apps).
  automint-worker-key  Ensure apps/backend/.env has GRACE_WORKER_GATEWAY_API_KEY (same as dev hook)
  rotate-worker-key    Soft-revoke the current worker key, mint a new one, rewrite apps/backend/.env
  worker   Run the agent-run queue worker (Redis BRPOP + process_run; same as dev-spawned worker)
  keys     Vault key inventory, backfill, rotation, verification (see docs/runbooks/key-rotation.md)
           axiom keys status | migrate-vault --apply | rotate --new-kek-b64 <b64> --apply | verify
  stop     Stop app processes and docker compose stop (keeps volumes)
  fresh    Stop, docker compose down -v, then full dev stack from clean DB
  status   Show postgres/redis/backend/frontend/worker status (use --json for machine-readable)
  logs     tail -f .axiom/last-session.log
  test     Run CI-equivalent checks (backend ruff/mypy/pytest+cov; frontend tsc/build/test)
           Use: axiom test --fast  (pytest + vitest only)
  help     Show this help

Examples:
  ./axiom dev
  ./axiom dev --no-start
  ./axiom automint-worker-key
  ./axiom rotate-worker-key
  ./axiom keys status
  ./axiom worker
  ./axiom stop
EOF
}
