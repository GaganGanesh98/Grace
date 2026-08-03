#!/usr/bin/env bash
# Smoke test: verify backend + gateway converge on the same evidence_key_id.
# NOT part of CI — touches real ports (8000, 8001).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
DOTENV="${REPO_ROOT}/apps/backend/.env"
BACKUP="${DOTENV}.backup.smoke"
AXIOM="${REPO_ROOT}/axiom"

cleanup() {
  echo "[smoke] cleaning up..."
  "${AXIOM}" stop 2>/dev/null || true
  if [[ -f "${BACKUP}" ]]; then
    mv "${BACKUP}" "${DOTENV}"
    echo "[smoke] restored .env from backup"
  fi
}
trap cleanup EXIT

# 1. Backup .env
cp "${DOTENV}" "${BACKUP}"
echo "[smoke] backed up .env"

# 2. Strip Phase-2 key lines
sed -i '/^AXIOM_EVIDENCE_KEY_B64=/d;/^AXIOM_ED25519_/d;/^AXIOM_ML_DSA_/d' "${DOTENV}"
echo "[smoke] stripped Phase-2 key lines from .env"

# 3. Start axiom dev in background, capture output
LOG=$(mktemp /tmp/axiom-smoke-XXXX.log)
"${AXIOM}" dev >"${LOG}" 2>&1 &
DEV_PID=$!
echo "[smoke] started axiom dev (PID=${DEV_PID}), waiting ~12s..."
sleep 12

# 4. Health checks
echo "[smoke] checking health endpoints..."
curl -sf http://127.0.0.1:8000/healthz >/dev/null && echo "[smoke] backend /healthz OK" || echo "[smoke] backend /healthz FAIL"
curl -sf http://127.0.0.1:8001/healthz >/dev/null && echo "[smoke] gateway /healthz OK" || echo "[smoke] gateway /healthz FAIL"

# 5. Extract evidence_key_ids from log
echo "[smoke] scanning logs for evidence_key_id..."
BACKEND_ID=$(grep -oP 'axiom\.startup.*?evidence_key_id=\K[a-f0-9]+' "${LOG}" | head -1)
GATEWAY_ID=$(grep -oP 'axiom\.gateway\.startup.*?evidence_key_id=\K[a-f0-9]+' "${LOG}" | head -1)

echo "[smoke] backend  evidence_key_id=${BACKEND_ID:-NOT_FOUND}"
echo "[smoke] gateway  evidence_key_id=${GATEWAY_ID:-NOT_FOUND}"

if [[ -z "${BACKEND_ID}" ]] || [[ -z "${GATEWAY_ID}" ]]; then
  echo "[smoke] FAIL: could not find evidence_key_id in logs"
  cat "${LOG}"
  exit 1
fi

if [[ "${BACKEND_ID}" == "${GATEWAY_ID}" ]]; then
  echo "[smoke] PASS: both processes share the same evidence_key_id"
  exit 0
else
  echo "[smoke] FAIL: key mismatch backend=${BACKEND_ID} gateway=${GATEWAY_ID}"
  exit 1
fi
