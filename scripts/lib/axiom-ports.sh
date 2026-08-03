# shellcheck shell=bash
# Port listeners: app ports (8000/3000) vs docker infra (5433/6380).
# Phase 2.3: never kill unknown uvicorn on :8000. Phase 2.4: docker-proxy/rootlesskit on
# published DB/Redis host ports are expected Docker internals, not rogues.
: "${REPO_ROOT:?}"

readonly DOCKER_PROXY_PATTERNS=('docker-proxy' 'rootlesskit')

_cmdline_for_pid() {
  local pid=$1
  if [[ -r "/proc/${pid}/cmdline" ]]; then
    tr '\0' ' ' <"/proc/${pid}/cmdline"
  else
    echo ""
  fi
}

_matches_docker_proxy() {
  local line=$1
  local p
  for p in "${DOCKER_PROXY_PATTERNS[@]}"; do
    if [[ "${line}" == *"${p}"* ]]; then
      return 0
    fi
  done
  return 1
}

_listeners_on_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -F ":${port} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u
  else
    echo "axiom: need lsof or ss for port checks" >&2
    exit 1
  fi
}

axiom_assert_infra_ports_or_abort() {
  local port cmdline pid
  for port in "${AXIOM_PG_HOST_PORT}" "${AXIOM_REDIS_HOST_PORT}"; do
    for pid in $(_listeners_on_port "${port}"); do
      [[ -z "${pid}" ]] && continue
      cmdline="$(_cmdline_for_pid "${pid}")"
      if _matches_docker_proxy "${cmdline}"; then
        continue
      fi
      echo "axiom: port ${port} is held by an unexpected process (pid=${pid}): ${cmdline}" >&2
      echo "axiom: free the port or fix docker compose port publishing before continuing." >&2
      return 1
    done
  done
}

axiom_prepare_app_port() {
  local port=$1
  local kind=$2
  local pid cmdline
  for pid in $(_listeners_on_port "${port}"); do
    [[ -z "${pid}" ]] && continue
    cmdline="$(_cmdline_for_pid "${pid}")"
    if [[ "${kind}" == backend ]]; then
      if [[ "${cmdline}" == *uvicorn* ]] && [[ "${cmdline}" == *axiom.main:app* ]]; then
        kill -TERM "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
          kill -KILL "${pid}" 2>/dev/null || true
        fi
        continue
      fi
      echo "axiom: port ${port} is in use by a non-AXIOM process (pid=${pid}): ${cmdline}" >&2
      echo "axiom: stop that process or pick another port; will not kill unknown listeners." >&2
      return 1
    fi
    if [[ "${kind}" == frontend ]]; then
      if [[ "${cmdline}" == *next* ]] && { [[ "${cmdline}" == *"next dev"* ]] || [[ "${cmdline}" == *next-server* ]]; }; then
        kill -TERM "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
          kill -KILL "${pid}" 2>/dev/null || true
        fi
        continue
      fi
      echo "axiom: port ${port} is in use by a non-AXIOM process (pid=${pid}): ${cmdline}" >&2
      echo "axiom: stop that process or pick another port; will not kill unknown listeners." >&2
      return 1
    fi
    if [[ "${kind}" == gateway ]]; then
      if [[ "${cmdline}" == *uvicorn* ]] && [[ "${cmdline}" == *axiom.gateway.app:app* ]]; then
        kill -TERM "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
          kill -KILL "${pid}" 2>/dev/null || true
        fi
        continue
      fi
      echo "axiom: port ${port} is in use by a non-AXIOM process (pid=${pid}): ${cmdline}" >&2
      echo "axiom: stop that process or pick another port; will not kill unknown listeners." >&2
      return 1
    fi
  done
}
