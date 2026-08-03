#!/usr/bin/env bash
# Integration smoke for worker API key automint (no full ./axiom dev).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "skip: uv not installed" >&2
  exit 0
fi

(cd apps/backend && uv run python -c "from axiom.cli import automint; assert automint.DEV_USER_EMAIL")

echo "automint: Python module import OK"

(
  export CI=true
  unset AXIOM_WORKER_GATEWAY_API_KEY
  cd apps/backend
  uv run python -m axiom.cli.automint ensure
)
echo "automint: CI=true ensure exited 0"

env_path="${REPO_ROOT}/apps/backend/.env"
if [[ -f "${env_path}" ]]; then
  before="$(sha256sum "${env_path}" | awk '{print $1}')"
  (
    export CI=true
    export GITHUB_ACTIONS=
    unset AXIOM_WORKER_GATEWAY_API_KEY
    cd "${REPO_ROOT}/apps/backend"
    uv run python -m axiom.cli.automint ensure
  )
  after="$(sha256sum "${env_path}" | awk '{print $1}')"
  if [[ "${before}" != "${after}" ]]; then
    echo "automint: FAIL .env changed under CI=true" >&2
    exit 1
  fi
  echo "automint: .env unchanged under CI=true"
fi

echo "automint: all checks passed"
