# shellcheck shell=bash
: "${REPO_ROOT:?}"

axiom_run_logs() {
  if [[ ! -f "${AXIOM_LOG}" ]]; then
    echo "axiom: no session log at ${AXIOM_LOG} yet. Run ./axiom dev first." >&2
    exit 1
  fi
  tail -f "${AXIOM_LOG}"
}
