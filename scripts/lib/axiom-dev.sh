# shellcheck shell=bash
: "${REPO_ROOT:?}"
# shellcheck source=axiom-stop.sh
source "${REPO_ROOT}/scripts/lib/axiom-stop.sh"

_axiom_healthz_ok() {
  curl -sf "http://127.0.0.1:${AXIOM_BACKEND_PORT}/healthz" 2>/dev/null | grep -q '"ok"' || return 1
}

_axiom_gateway_healthz_ok() {
  curl -sf "http://127.0.0.1:${AXIOM_GATEWAY_PORT}/healthz" 2>/dev/null | grep -q '"ok"' || return 1
}

_axiom_frontend_http_ok() {
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${AXIOM_FRONTEND_PORT}/" 2>/dev/null || echo 000)"
  [[ "${code}" == 200 || "${code}" == 307 ]]
}

_axiom_worker_ok() {
  [[ -f "${AXIOM_PID_WORKER}" ]] || return 1
  local pid
  pid="$(cat "${AXIOM_PID_WORKER}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

_axiom_all_live() {
  local st
  st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' axiom-postgres 2>/dev/null || echo missing)"
  [[ "${st}" == healthy ]] || return 1
  axiom_compose exec -T redis redis-cli PING 2>/dev/null | grep -qx PONG || return 1
  _axiom_healthz_ok || return 1
  _axiom_gateway_healthz_ok || return 1
  _axiom_frontend_http_ok || return 1
  _axiom_worker_ok || return 1
}

_axiom_dev_trap() {
  if ((AXIOM_SHUTTING_DOWN == 1)); then
    exit 130
  fi
  AXIOM_SHUTTING_DOWN=1
  axiom_log_tagged pg green "axiom: shutdown (Ctrl+C)"
  axiom_shutdown_sequence
  exit 0
}

axiom_run_dev() {
  local no_start=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-start) no_start=1; shift ;;
      *) break ;;
    esac
  done

  require_docker_group
  if ! docker info >/dev/null 2>&1; then
    echo "axiom: docker daemon not reachable (is Docker running?)" >&2
    exit 1
  fi

  if _axiom_all_live 2>/dev/null; then
    echo "AXIOM dev already running (health checks passed). Use ./axiom stop to restart."
    exit 0
  fi

  ensure_axiom_dir
  trap '_axiom_dev_trap' INT TERM

  if ! axiom_assert_infra_ports_or_abort; then
    axiom_shutdown_sequence
    exit 1
  fi

  axiom_log_tagged pg green "Starting Postgres + Redis..."
  axiom_compose up -d postgres redis || {
    axiom_shutdown_sequence
    exit 1
  }

  wait_postgres_healthy 60 || {
    axiom_log_tagged pg green "axiom: postgres did not become healthy in time"
    axiom_shutdown_sequence
    exit 1
  }
  axiom_log_tagged pg green "Postgres healthy."

  wait_redis_pong 15 || {
    axiom_log_tagged redis red "axiom: redis did not respond to PING in time"
    axiom_shutdown_sequence
    exit 1
  }
  axiom_log_tagged redis red "Redis PONG."

  axiom_log_tagged pg green "Running migrations..."
  (cd "${REPO_ROOT}/apps/backend" && uv run alembic upgrade head) || {
    axiom_log_tagged pg green "axiom: migrations failed"
    axiom_shutdown_sequence
    exit 1
  }

  # shellcheck source=axiom-ensure-test-db.sh
  source "${REPO_ROOT}/scripts/lib/axiom-ensure-test-db.sh"
  axiom_ensure_test_database || {
    axiom_log_tagged pg green "axiom: could not ensure axiom_test database"
    axiom_shutdown_sequence
    exit 1
  }
  axiom_log_tagged pg green "Running migrations on axiom_test (pytest isolation)..."
  axiom_migrate_test_database || {
    axiom_log_tagged pg green "axiom: axiom_test migrations failed"
    axiom_shutdown_sequence
    exit 1
  }

  # shellcheck source=axiom-automint.sh
  source "${REPO_ROOT}/scripts/lib/axiom-automint.sh"
  _axiom_ensure_worker_gateway_api_key || {
    axiom_log_tagged pg green "axiom: worker API key automint failed"
    axiom_shutdown_sequence
    exit 1
  }

  axiom_log_tagged keys magenta "Preflighting Phase-2 signing keys..."
  (cd "${REPO_ROOT}/apps/backend" && uv run python -c \
    "from axiom.services.receipt.keys import preflight_ensure_keys; \
     ids = preflight_ensure_keys(); \
     print(f'[keys] ready evidence_key_id={ids[\"evidence_key_id\"][:16]}')" \
    ) || { axiom_log_tagged keys magenta "Phase-2 key preflight failed"; axiom_shutdown_sequence; exit 1; }

  if ((no_start == 1)); then
    axiom_log_tagged pg green "axiom dev --no-start: Postgres + migrations + automint done; skipping app processes."
    return 0
  fi

  if ! _axiom_healthz_ok; then
    if ! axiom_prepare_app_port "${AXIOM_BACKEND_PORT}" backend; then
      axiom_shutdown_sequence
      exit 1
    fi
    if [[ -f "${REPO_ROOT}/.env.dev" ]]; then
      set -a
      # shellcheck disable=SC1091
      source "${REPO_ROOT}/.env.dev"
      set +a
    fi
    (
      cd "${REPO_ROOT}/apps/backend"
      uv run uvicorn axiom.main:app --reload --host 0.0.0.0 --port "${AXIOM_BACKEND_PORT}" &
      echo $! >"${AXIOM_PID_BACKEND}"
      wait "$(cat "${AXIOM_PID_BACKEND}")"
    ) 2>&1 | while IFS= read -r line || [[ -n "${line}" ]]; do
      axiom_log_tagged backend cyan "${line}"
    done &
    if ! wait_for_http "http://127.0.0.1:${AXIOM_BACKEND_PORT}/healthz" 30 "backend /healthz"; then
      axiom_shutdown_sequence
      exit 1
    fi
  else
    rm -f "${AXIOM_PID_BACKEND}"
    axiom_log_tagged backend cyan "backend already responding on :${AXIOM_BACKEND_PORT}; skipping start"
  fi

  if ! _axiom_gateway_healthz_ok; then
    if ! axiom_prepare_app_port "${AXIOM_GATEWAY_PORT}" gateway; then
      axiom_shutdown_sequence
      exit 1
    fi
    if [[ -f "${REPO_ROOT}/.env.dev" ]]; then
      set -a
      # shellcheck disable=SC1091
      source "${REPO_ROOT}/.env.dev"
      set +a
    fi
    (
      cd "${REPO_ROOT}/apps/backend"
      uv run uvicorn axiom.gateway.app:app --reload --host 0.0.0.0 --port "${AXIOM_GATEWAY_PORT}" &
      echo $! >"${AXIOM_PID_GATEWAY}"
      wait "$(cat "${AXIOM_PID_GATEWAY}")"
    ) 2>&1 | while IFS= read -r line || [[ -n "${line}" ]]; do
      axiom_log_tagged gateway yellow "${line}"
    done &
    if ! wait_for_http "http://127.0.0.1:${AXIOM_GATEWAY_PORT}/healthz" 30 "gateway /healthz"; then
      axiom_shutdown_sequence
      exit 1
    fi
  else
    rm -f "${AXIOM_PID_GATEWAY}"
    axiom_log_tagged gateway yellow "gateway already responding on :${AXIOM_GATEWAY_PORT}; skipping start"
  fi

  if ! _axiom_frontend_http_ok; then
    if ! axiom_prepare_app_port "${AXIOM_FRONTEND_PORT}" frontend; then
      axiom_shutdown_sequence
      exit 1
    fi
    (
      cd "${REPO_ROOT}/apps/frontend"
      npm run dev &
      echo $! >"${AXIOM_PID_FRONTEND}"
      wait "$(cat "${AXIOM_PID_FRONTEND}")"
    ) 2>&1 | while IFS= read -r line || [[ -n "${line}" ]]; do
      axiom_log_tagged frontend magenta "${line}"
    done &
    if ! wait_for_http "http://127.0.0.1:${AXIOM_FRONTEND_PORT}/" 30 "frontend root"; then
      axiom_shutdown_sequence
      exit 1
    fi
  else
    rm -f "${AXIOM_PID_FRONTEND}"
    axiom_log_tagged frontend magenta "frontend already responding on :${AXIOM_FRONTEND_PORT}; skipping start"
  fi

  if ! _axiom_worker_ok; then
    if [[ -x "${REPO_ROOT}/apps/backend/.venv/bin/python" ]]; then
      if [[ -f "${REPO_ROOT}/.env.dev" ]]; then
        set -a
        # shellcheck disable=SC1091
        source "${REPO_ROOT}/.env.dev"
        set +a
      fi
      (
        cd "${REPO_ROOT}/apps/backend"
        export DATABASE_URL="${AXIOM_DEV_DATABASE_URL}"
        unset TEST_DATABASE_URL
        .venv/bin/python -m axiom.workers.agent_worker &
        echo $! >"${AXIOM_PID_WORKER}"
        wait "$(cat "${AXIOM_PID_WORKER}")"
      ) 2>&1 | while IFS= read -r line || [[ -n "${line}" ]]; do
        axiom_log_tagged worker blue "${line}"
      done &
    else
      axiom_log_tagged worker blue "axiom: apps/backend/.venv missing; skipping agent worker (cd apps/backend && uv sync)"
    fi
  else
    axiom_log_tagged worker blue "agent worker already running (pid file); skipping start"
  fi

  echo ""
  echo "AXIOM dev is up:"
  echo "  Backend:  http://127.0.0.1:${AXIOM_BACKEND_PORT}"
  echo "  Gateway:  http://127.0.0.1:${AXIOM_GATEWAY_PORT}"
  echo "  API docs: http://127.0.0.1:${AXIOM_BACKEND_PORT}/docs"
  echo "  Frontend: http://127.0.0.1:${AXIOM_FRONTEND_PORT}"
  echo "  Worker:   agent runs queue (see .axiom/worker.pid)"
  echo ""
  echo "Ensure apps/frontend/.env.local sets API_URL=http://127.0.0.1:${AXIOM_BACKEND_PORT} (see apps/frontend/.env.example)."
  echo "Ctrl+C stops all services; ./axiom stop stops without starting."

  while true; do sleep 86400; done &
  local blocker=$!
  wait "${blocker}" 2>/dev/null || true
}
