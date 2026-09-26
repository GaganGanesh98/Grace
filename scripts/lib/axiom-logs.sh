# shellcheck shell=bash
: "${REPO_ROOT:?}"

axiom_run_logs() {
  if [[ ! -f "${GRACE_LOG}" ]]; then
    echo "axiom: no session log at ${GRACE_LOG} yet. Run ./axiom dev first." >&2
    exit 1
  fi
  tail -f "${GRACE_LOG}"
}
