# shellcheck shell=bash
: "${REPO_ROOT:?}"

_status_pg() {
  local st name
  name="$(docker inspect -f '{{.Name}}' axiom-postgres 2>/dev/null || echo "")"
  st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' axiom-postgres 2>/dev/null || echo missing)"
  if [[ -n "${name}" && "${st}" == healthy ]]; then
    echo "ok|Postgres healthy|${st}"
  elif [[ -n "${name}" ]]; then
    echo "bad|Postgres container running but not healthy (${st})|${st}"
  else
    echo "bad|Postgres container not found|missing"
  fi
}

_status_redis() {
  if ! docker inspect axiom-redis >/dev/null 2>&1; then
    echo "bad|Redis container not found|missing"
    return
  fi
  if axiom_compose exec -T redis redis-cli PING 2>/dev/null | grep -qx PONG; then
    echo "ok|PONG|PONG"
  else
    echo "bad|redis-cli PING failed|error"
  fi
}

_status_backend() {
  local code pid
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${AXIOM_BACKEND_PORT}/healthz" 2>/dev/null || echo 000)"
  if [[ "${code}" == 200 ]]; then
    pid="$(_listeners_on_port "${AXIOM_BACKEND_PORT}" | head -1 || echo "")"
    echo "ok|/healthz ${code}|${pid}"
  else
    echo "bad|/healthz ${code}|"
  fi
}

_status_frontend() {
  local code pid
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${AXIOM_FRONTEND_PORT}/" 2>/dev/null || echo 000)"
  pid="$(_listeners_on_port "${AXIOM_FRONTEND_PORT}" | head -1 || echo "")"
  if [[ "${code}" == 200 || "${code}" == 307 ]]; then
    echo "ok|HTTP ${code}|${pid}"
  else
    echo "bad|HTTP ${code}|${pid}"
  fi
}

_status_worker() {
  if [[ ! -f "${AXIOM_PID_WORKER}" ]]; then
    echo "bad|no pid file|"
    return
  fi
  local pid
  pid="$(cat "${AXIOM_PID_WORKER}" 2>/dev/null || true)"
  [[ -z "${pid}" ]] && echo "bad|empty pid file|" && return
  if kill -0 "${pid}" 2>/dev/null; then
    echo "ok|process alive|${pid}"
  else
    echo "bad|stale pid file|${pid}"
  fi
}

_status_emit_json() {
  local pg="$1" redis="$2" be="$3" fe="$4" worker="$5"
  IFS='|' read -r pg_ok _ _ <<<"${pg}"
  IFS='|' read -r r_ok _ _ <<<"${redis}"
  IFS='|' read -r b_ok b_msg b_pid <<<"${be}"
  IFS='|' read -r f_ok f_msg f_pid <<<"${fe}"
  IFS='|' read -r w_ok w_msg w_pid <<<"${worker}"
  local pg_b r_b b_b f_b w_b
  pg_b="false"
  r_b="false"
  b_b="false"
  f_b="false"
  w_b="false"
  [[ "${pg_ok}" == ok ]] && pg_b="true"
  [[ "${r_ok}" == ok ]] && r_b="true"
  [[ "${b_ok}" == ok ]] && b_b="true"
  [[ "${f_ok}" == ok ]] && f_b="true"
  [[ "${w_ok}" == ok ]] && w_b="true"
  printf '{"postgres":{"ok":%s,"host_port":%s,"container_port":5432},"redis":{"ok":%s,"host_port":%s,"container_port":6379},"backend":{"ok":%s,"port":%s,"detail":"%s","pid":"%s"},"frontend":{"ok":%s,"port":%s,"detail":"%s","pid":"%s"},"worker":{"ok":%s,"detail":"%s","pid":"%s"}}\n' \
    "${pg_b}" "${AXIOM_PG_HOST_PORT}" \
    "${r_b}" "${AXIOM_REDIS_HOST_PORT}" \
    "${b_b}" "${AXIOM_BACKEND_PORT}" "${b_msg}" "${b_pid}" \
    "${f_b}" "${AXIOM_FRONTEND_PORT}" "${f_msg}" "${f_pid}" \
    "${w_b}" "${w_msg}" "${w_pid}"
}

axiom_run_status() {
  local json=0
  if [[ "${1:-}" == "--json" ]]; then
    json=1
  fi

  if ! groups | grep -qw docker; then
    cat <<'EOF' >&2
✗ Your user is not in the docker group.
  Run this once, then log out and back in (or newgrp docker):
    sudo usermod -aG docker $USER && newgrp docker
  More: docs/dev-setup.md
EOF
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "axiom: docker daemon not reachable (is Docker running?)" >&2
    exit 1
  fi

  local pg redis be fe worker
  pg="$(_status_pg)"
  redis="$(_status_redis)"
  be="$(_status_backend)"
  fe="$(_status_frontend)"
  worker="$(_status_worker)"

  if ((json == 1)); then
    _status_emit_json "${pg}" "${redis}" "${be}" "${fe}" "${worker}"
  else
    echo "AXIOM status"
    IFS='|' read -r ok msg extra <<<"${pg}"
    if [[ "${ok}" == ok ]]; then
      echo "  postgres: ✓ running on :${AXIOM_PG_HOST_PORT} → container :5432 (healthy, container=axiom-postgres)"
    else
      echo "  postgres: ✗ not running (${msg})"
    fi
    IFS='|' read -r ok msg extra <<<"${redis}"
    if [[ "${ok}" == ok ]]; then
      echo "  redis:    ✓ running on :${AXIOM_REDIS_HOST_PORT} (${extra}, container=axiom-redis)"
    else
      echo "  redis:    ✗ not running (${msg})"
    fi
    IFS='|' read -r ok msg extra <<<"${be}"
    if [[ "${ok}" == ok ]]; then
      echo "  backend:  ✓ running on :${AXIOM_BACKEND_PORT} (${msg}, pid=${extra:-?})"
    else
      echo "  backend:  ✗ not running (${msg})"
    fi
    IFS='|' read -r ok msg extra <<<"${fe}"
    if [[ "${ok}" == ok ]]; then
      echo "  frontend: ✓ running on :${AXIOM_FRONTEND_PORT} (${msg}, pid=${extra:-?})"
    else
      echo "  frontend: ✗ not running (${msg})"
    fi
    IFS='|' read -r ok msg extra <<<"${worker}"
    if [[ "${ok}" == ok ]]; then
      echo "  worker:   ✓ agent queue (${msg}, pid=${extra:-?})"
    else
      echo "  worker:   ✗ not running (${msg})"
    fi
  fi

  IFS='|' read -r pg_ok _ <<<"${pg}"
  IFS='|' read -r r_ok _ <<<"${redis}"
  IFS='|' read -r b_ok _ <<<"${be}"
  IFS='|' read -r f_ok _ <<<"${fe}"
  IFS='|' read -r w_ok _ <<<"${worker}"
  if [[ "${pg_ok}" == ok && "${r_ok}" == ok && "${b_ok}" == ok && "${f_ok}" == ok && "${w_ok}" == ok ]]; then
    exit 0
  fi
  exit 1
}
