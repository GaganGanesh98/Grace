# shellcheck shell=bash
# Create Postgres database axiom_test (for pytest isolation) if missing.
# Sourced from axiom-dev.sh after Postgres is healthy.

axiom_ensure_test_database() {
  local out
  out="$(axiom_compose exec -T postgres psql -U axiom -d axiom -tAc "SELECT 1 FROM pg_database WHERE datname='axiom_test'" 2>/dev/null || echo "")"
  out="$(echo -n "${out}" | tr -d '[:space:]')"
  if [[ "${out}" == "1" ]]; then
    return 0
  fi
  axiom_log_tagged pg green "Creating database axiom_test (pytest / integration tests; isolated from dev DB axiom)..."
  axiom_compose exec -T postgres psql -U axiom -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE axiom_test OWNER axiom;"
}

axiom_migrate_test_database() {
  (
    cd "${REPO_ROOT}/apps/backend" || exit 1
    DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:${AXIOM_PG_HOST_PORT}/axiom_test}" \
      uv run alembic upgrade head
  ) || return 1
}
