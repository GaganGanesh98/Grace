# Governance Chains (Phase 2.5.1) — Build Report

## What was built

- **Database**: New `governance_chains` table plus nullable `governance_intents.chain_id` (FK) via migration `f7e8d9c0b1a2_governance_chains.py`.
- **Models**: `GovernanceChain` ORM model; `GovernanceIntent.chain_id` and optional `chain` relationship.
- **Schemas**: `GovernRequest.workflow`, `GovernRequest.chain_id`, `GovernResponse.chain_id`, `ChainCloseRequest`, `ChainSummary`, `ChainListResponse`.
- **Service**: `src/axiom/services/governance/chain.py` — create/get/resolve chain, stats updates (govern vs report split), chain hash (`SHA-256` over concatenated sealed receipt hashes in chronological order), dual signing (same keys as receipt sealing: Ed25519 PEM + ML-DSA via `ml_dsa` module used elsewhere), list/detail helpers, auto-close of stale active chains per project.
- **Pipeline integration**:
  - `POST /v1/governance/govern`: piggyback `auto_close_stale_chains` (30 minutes), `get_or_create_chain`, `declare_intent(..., chain_id=...)`, `update_chain_stats` with verdict only; response includes `chain_id` when applicable.
  - `POST /v1/governance/report`: after seal, `update_chain_stats` with verification only (no second `total_actions` bump).
- **New router** `src/axiom/routers/v1/chains.py`, mounted at `/v1/chains` in `main.py`.

## API endpoints (examples)

Replace `API_KEY`, `BASE` (e.g. `http://localhost:8000`), `PROJECT` context is implied by the API key.

### Start a workflow (auto-create chain)

```bash
curl -sS -X POST "$BASE/v1/governance/govern" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-bot",
    "action_type": "tool.http.get",
    "target": "https://example.com/q",
    "risk": "low",
    "workflow": "Tesla earnings research"
  }'
```

Response includes `"chain_id": "<uuid>"` when a chain is created.

### Add another action to the same chain

```bash
curl -sS -X POST "$BASE/v1/governance/govern" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-bot",
    "action_type": "tool.http.get",
    "target": "https://example.com/q2",
    "risk": "low",
    "chain_id": "<CHAIN_UUID>"
  }'
```

### List chains

```bash
curl -sS "$BASE/v1/chains?page=1&per_page=20" \
  -H "Authorization: Bearer $API_KEY"
```

Optional filter: `&status=active` (or `sealed`, `auto_closed`).

### Get one chain (summary + receipt records)

```bash
curl -sS "$BASE/v1/chains/<CHAIN_UUID>" \
  -H "Authorization: Bearer $API_KEY"
```

### Close and seal a chain (dual signatures)

```bash
curl -sS -X POST "$BASE/v1/chains/<CHAIN_UUID>/close" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{}'
```

Standalone govern (no `workflow` / `chain_id`) is unchanged; `chain_id` in the response is omitted or `null`.

## Chain sealing cryptography

- **Payload**: `chain_hash = SHA256(hash1 || hash2 || ...)` where each `hash` is the **32-byte sealed `governance_receipts.receipt_hash`**, ordered by `governance_receipts.created_at`. Pending receipts are excluded (no hash yet).
- **Signatures**: `chain_hash` is signed with the process-wide keys from `get_signing_keys()` — **Ed25519** (`ed25519.sign(private_pem, chain_hash)`) and **ML-DSA-65** (`ml_dsa.sign(ml_dsa_private, chain_hash)`), matching the stack used for receipt sealing.
- **Storage**: `governance_chains.chain_hash`, `ed25519_sig`, `ml_dsa_sig`, `key_id` (Ed25519 key id).
- **Verification (read API)**: `GET /v1/chains/{id}` populates `chain_signature` with `{"ed25519": bool, "ml_dsa_65": bool}` when the chain is sealed (`sealed` or `auto_closed`) and hashes/signatures exist.

## Auto-close mechanism

- On **each** `POST /v1/governance/govern`, after authentication, the service runs `auto_close_stale_chains(project_id, timeout_minutes=30)`.
- Active chains with `last_activity` older than 30 minutes are **closed and sealed** (same hash + dual signatures as manual close) with `status = auto_closed`.
- `last_activity` is updated when govern increments stats (verdict path) and when report increments compliance stats.
- Processing is capped (50 chains per call) to keep govern latency bounded.

## Decisions

- **Stats split**: Verdict counters and `total_actions` increment on govern; `compliant` / `non_compliant` increment on report when verification is `pass` / `fail` (`skipped` does not increment).
- **ML-DSA module**: Uses `axiom.services.crypto.ml_dsa` (same as receipt sealing / tests), not `ml_dsa_65.py`, so keys from `get_signing_keys()` align with existing signing.
- **Invalid `chain_id`**: HTTP **400** with a clear message (wrong project, wrong agent, not active, or missing).
- **Close on already sealed chain**: HTTP **409**.

## Test results

Last run:

```text
cd apps/backend && uv run pytest --no-cov -q
```

Result: **all tests passed** (full suite including `tests/unit/test_governance/test_chains.py`). Some crypto tests may skip when ML-DSA backends are unavailable; in this environment ML-DSA was available.

Ruff: new/changed application files under `src/axiom` for this feature pass `ruff check` and `ruff format`.

## Files touched (summary)

| New | Modified |
|-----|----------|
| `alembic/versions/f7e8d9c0b1a2_governance_chains.py` | `src/axiom/models/governance.py`, `models/__init__.py` |
| `src/axiom/services/governance/chain.py` | `src/axiom/schemas/governance.py` |
| `src/axiom/routers/v1/chains.py` | `src/axiom/routers/v1/governance.py`, `intent.py`, `main.py` |
| `tests/unit/test_governance/test_chains.py` | — |
