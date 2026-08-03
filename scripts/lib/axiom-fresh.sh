# shellcheck shell=bash
: "${REPO_ROOT:?}"

axiom_run_fresh() {
  require_docker_group
  # shellcheck source=axiom-stop.sh
  source "${REPO_ROOT}/scripts/lib/axiom-stop.sh"
  if ! docker info >/dev/null 2>&1; then
    echo "axiom: docker daemon not reachable (is Docker running?)" >&2
    exit 1
  fi
  axiom_shutdown_sequence
  echo "→ docker compose down -v (removing named volumes)..."
  (cd "${REPO_ROOT}" && docker compose down -v)
  # shellcheck source=axiom-dev.sh
  source "${REPO_ROOT}/scripts/lib/axiom-dev.sh"
  axiom_run_dev
}
