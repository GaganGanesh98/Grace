# shellcheck shell=bash
: "${REPO_ROOT:?}"

_axiom_test_fail() {
  echo "axiom test: FAILED at step: $1" >&2
  exit 1
}

_axiom_test_run() {
  local label=$1
  shift
  echo "→ ${label}"
  if ! "$@"; then
    _axiom_test_fail "${label}"
  fi
}

axiom_run_test() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "axiom: uv is not on PATH (install uv: https://docs.astral.sh/uv/)" >&2
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "axiom: npm is not on PATH" >&2
    exit 1
  fi

  # Isolate pytest from the dev DB (axiom) + Redis DB 0; see apps/backend/tests/conftest.py
  export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:5433/axiom_test}"
  export TEST_REDIS_URL="${TEST_REDIS_URL:-redis://127.0.0.1:6380/1}"

  if [[ "${1:-}" == "--fast" ]]; then
    _axiom_test_run "backend pytest (tests/)" bash -c "cd \"${REPO_ROOT}/apps/backend\" && uv run pytest tests/ -q"
    _axiom_test_run "frontend vitest (npm run test)" bash -c "cd \"${REPO_ROOT}/apps/frontend\" && npm run test"
    echo "axiom test --fast: all steps passed."
    return 0
  fi

  _axiom_test_run "backend ruff check" bash -c "cd \"${REPO_ROOT}/apps/backend\" && uv run ruff check ."
  _axiom_test_run "backend ruff format --check" bash -c "cd \"${REPO_ROOT}/apps/backend\" && uv run ruff format --check ."
  _axiom_test_run "backend mypy" bash -c "cd \"${REPO_ROOT}/apps/backend\" && uv run mypy src"
  _axiom_test_run "backend pytest + coverage" bash -c "cd \"${REPO_ROOT}/apps/backend\" && uv run pytest --cov=axiom --cov-fail-under=80 -q"
  _axiom_test_run "frontend tsc --noEmit" bash -c "cd \"${REPO_ROOT}/apps/frontend\" && npx tsc --noEmit"
  _axiom_test_run "frontend build" bash -c "cd \"${REPO_ROOT}/apps/frontend\" && npm run build"
  _axiom_test_run "frontend vitest" bash -c "cd \"${REPO_ROOT}/apps/frontend\" && npm run test"

  _axiom_test_run "axiom CLI smoke tests" bash "${REPO_ROOT}/scripts/lib/tests/test_axiom_cli.sh"
  echo "axiom test: all steps passed."
}
