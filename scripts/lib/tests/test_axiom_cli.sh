#!/usr/bin/env bash
# Smoke tests for ./axiom (invoked by ./axiom test). Pure bash.
set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
readonly AX="${REPO_ROOT}/axiom"

_fail() {
  echo "test_axiom_cli: $1" >&2
  exit 1
}

_out() {
  "${AX}" "$@" 2>&1
}

echo "→ axiom help lists subcommands"
h="$(_out help)"
echo "${h}" | grep -q '^\s*dev\b' || _fail "missing dev in help"
echo "${h}" | grep -q 'stop' || _fail "missing stop"
echo "${h}" | grep -q 'fresh' || _fail "missing fresh"
echo "${h}" | grep -q 'status' || _fail "missing status"
echo "${h}" | grep -q 'logs' || _fail "missing logs"
echo "${h}" | grep -q 'test' || _fail "missing test"
echo "${h}" | grep -q 'help' || _fail "missing help"

echo "→ axiom (no args) exits 0"
_out | grep -q 'Usage:' || _fail "no-arg should show usage"

echo "→ axiom unknown-command exits non-zero"
set +e
_out not-a-real-command
ec=$?
set -e
[[ "${ec}" -ne 0 ]] || _fail "unknown command should be non-zero"
# Avoid SIGPIPE / pipefail false negatives from `grep -q` closing the pipe early.
unk="$(_out not-a-real-command 2>&1 || true)"
[[ "${unk}" == *"unknown command:"* ]] || _fail "unknown command message"

echo "→ axiom status (may exit 0 or 1)"
set +e
_out status
sc=$?
set -e
[[ "${sc}" == 0 || "${sc}" == 1 ]] || _fail "status should exit 0 or 1"

echo "→ axiom_prepare_app_port aborts on non-AXIOM listener"
export REPO_ROOT
# shellcheck source=../axiom-common.sh
source "${REPO_ROOT}/scripts/lib/axiom-common.sh"
port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()')"
python3 -m http.server "${port}" --bind 127.0.0.1 >/dev/null 2>&1 &
srv=$!
sleep 0.3
set +e
axiom_prepare_app_port "${port}" backend
kc=$?
set -e
kill "${srv}" 2>/dev/null || true
wait "${srv}" 2>/dev/null || true
[[ "${kc}" -ne 0 ]] || _fail "expected non-zero when port held by http.server"

echo "test_axiom_cli: OK"
