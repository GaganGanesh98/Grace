# shellcheck shell=bash
# Auto-mint AXIOM_WORKER_GATEWAY_API_KEY into apps/backend/.env (dev only).
# Sourced from axiom-dev.sh after Postgres is healthy and migrations ran.

_axiom_ensure_worker_gateway_api_key() {
  if [[ "${CI:-}" == "true" ]] || [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    axiom_log_tagged pg green "Worker API key automint skipped (CI)."
    return 0
  fi
  if [[ -n "${AXIOM_WORKER_GATEWAY_API_KEY:-}" ]]; then
    axiom_log_tagged pg green "Auto-mint skipped (explicit key provided)."
    return 0
  fi
  (
    cd "${REPO_ROOT}/apps/backend" || exit 1
    uv run python -m axiom.cli.automint ensure
  ) || return 1
}
