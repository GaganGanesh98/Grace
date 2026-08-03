# shellcheck shell=bash
: "${REPO_ROOT:?}"

_axiom_kill_pidfile() {
  local f=$1
  [[ ! -f "${f}" ]] && return 0
  local pid
  pid="$(cat "${f}" 2>/dev/null || true)"
  rm -f "${f}"
  [[ -z "${pid}" ]] && return 0
  if kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null || true
    local i=0
    while ((i < 50)) && kill -0 "${pid}" 2>/dev/null; do
      sleep 0.1
      ((i += 1)) || true
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
}

# Stops Next + uvicorn, then compose stop (preserves volumes).
axiom_shutdown_sequence() {
  _axiom_kill_pidfile "${AXIOM_PID_WORKER}"
  _axiom_kill_pidfile "${AXIOM_PID_FRONTEND}"
  _axiom_kill_pidfile "${AXIOM_PID_GATEWAY}"
  _axiom_kill_pidfile "${AXIOM_PID_BACKEND}"
  axiom_compose stop redis postgres 2>/dev/null || true
}

axiom_run_stop() {
  require_docker_group
  if ! docker info >/dev/null 2>&1; then
    echo "axiom: docker daemon not reachable (is Docker running?)" >&2
    exit 1
  fi
  axiom_shutdown_sequence
  echo "AXIOM stopped."
}
