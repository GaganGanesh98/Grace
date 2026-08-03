# Phase 2.5 Governance Engine — Build Report

## What was built

- **Alembic migration** `e5f6a7b8c9d0_governance_engine_tables.py`: tables `governance_intents`, `governance_verdicts`, `governance_receipts` with indexes on `project_id`, `intent_id`, `status`, and `created_at` where specified.
- **SQLAlchemy models** in `src/axiom/models/governance.py` (registered via `axiom.models` for metadata).
- **Pydantic schemas** appended to `src/axiom/schemas/governance.py` (`GovernRequest`, `ReportRequest`, `VerifyReceiptRequest`, `GovernResponse`, `ReportResponse`, `EngineReceiptResponse`, `GovernanceEngineVerifyResponse`). Legacy types (`GovernanceRequest`, `VerifyResponse` for GET `/v1/verify/{id}`, etc.) are unchanged.
- **Six service modules** under `src/axiom/services/governance/`: `intent.py`, `context.py`, `policy.py`, `verdict.py`, `verification.py` (execution checks + `verify_receipt_independent` for POST `/verify`), `receipt.py` (pending row, sealing, Merkle leaf cache, startup `load_governance_merkle_from_db`).
- **Starter policies** in `apps/backend/policies/*.yaml`.
- **Router** `src/axiom/routers/v1/governance.py`, mounted in `main.py` with prefix **`/v1/governance`** so this engine does not collide with the existing legacy **`POST /v1/govern`** pipeline.
- **Dependency**: `pyyaml` added to `pyproject.toml` for YAML policy loading.
- **App startup**: `lifespan` loads Merkle leaf sequences from sealed `governance_receipts` rows via `load_governance_merkle_from_db`.

## API endpoints (actual paths)

| Method | Path | Auth |
|--------|------|------|
| POST | `/v1/governance/govern` | API key (`govern:write`) |
| POST | `/v1/governance/report` | API key |
| GET | `/v1/governance/receipts/{receipt_id}` | API key, or optional `?share_token=` matching `intent.metadata.public_share_token` |
| POST | `/v1/governance/verify` | None |

### Example curl

**Govern (API key):**

```bash
curl -sS -X POST "http://localhost:8000/v1/governance/govern" \
  -H "Authorization: Bearer axm_<your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-1",
    "action_type": "tool.http.get",
    "target": "https://api.example.com/v1/x",
    "parameters": {},
    "risk": "low",
    "mode": "enforce",
    "metadata": {}
  }'
```

**Report execution:**

```bash
curl -sS -X POST "http://localhost:8000/v1/governance/report" \
  -H "Authorization: Bearer axm_<your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "receipt_id": "<uuid from govern>",
    "outcome": {
      "target": "https://api.example.com/v1/x",
      "action_type": "tool.http.get",
      "risk": "low"
    }
  }'
```

**Get receipt:**

```bash
curl -sS "http://localhost:8000/v1/governance/receipts/<receipt_id>" \
  -H "Authorization: Bearer axm_<your_api_key>"
```

**Public share (no API key):**

```bash
curl -sS "http://localhost:8000/v1/governance/receipts/<receipt_id>?share_token=<token_from_intent_metadata>"
```

**Independent verify:**

```bash
curl -sS -X POST "http://localhost:8000/v1/governance/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "receipt_json": "<canonical JSON string of signed payload>",
    "ed25519_signature": "<base64>",
    "ml_dsa_signature": "<base64>",
    "merkle_proof": ["<hex>", "..."],
    "merkle_root": "<hex>",
    "ed25519_public_key": "<PEM or base64 raw>",
    "ml_dsa_public_key": "<base64>",
    "leaf_index": 0,
    "tree_size": 1,
    "leaf_preimage_hex": null
  }'
```

## Policy evaluation (MVP)

- Policy file is chosen from `project.settings["governance_policy"]` (stem name, e.g. `starter-safe` → `policies/starter-safe.yaml`). If missing or file not found, **`starter-safe`** is used.
- Policy version string: `{stem}-v{version}` from YAML `version` field.
- Rules run **top to bottom**; first matching `condition` wins.
- Conditions supported: `true`, or `field == 'value'` for `risk`, `action_type`, or `target` compared to the intent.
- **Shadow mode** (`intent.mode == "shadow"`): API returns `verdict: "allow"` but the **stored** `governance_verdicts.verdict` remains the real policy outcome; response `reason` may note the shadowed verdict.

## Crypto integration

- **Receipt hash**: SHA-256 of RFC 8785 canonical JSON of `unsigned_receipt_for_sealing(...)` (see `receipt.py`).
- **Signing**: same canonical bytes signed with process **Ed25519** and **ML-DSA-65** (`dilithium-py`) via `axiom.services.receipt.keys.get_signing_keys()` and `axiom.services.crypto.ed25519` / `ml_dsa`.
- **Merkle**: RFC 6962-style tree from `axiom.services.crypto.merkle` (`build_tree`, `inclusion_proof`, `verify_inclusion`). Leaf preimage is the **32-byte `receipt_hash`** digest. Per-project in-memory leaf lists are hydrated on startup and extended on each seal; sealed rows remain the source of truth.

## Test results

- New tests live under `tests/unit/test_governance/`.
- Full suite was not executed in this environment because **Redis** (and optionally PostgreSQL) were not reachable from the test runner; run locally:

```bash
cd apps/backend && uv sync && uv run alembic upgrade head && uv run pytest --no-cov -q
```

## Decisions

1. **Route prefix `/v1/governance`** — avoids breaking existing **`/v1/govern`** and its tests while delivering the 7-stage engine under stable URLs.
2. **Schema names** — `EngineReceiptResponse` / `VerifyReceiptRequest` / `GovernanceEngineVerifyResponse` avoid clashing with existing `VerifyResponse` (GET `/v1/verify/{id}`) and legacy `GovernanceRequest` / `GovernanceResponse`.
3. **JWT on govern** — not wired separately; **`require_api_key`** matches legacy `/v1/govern`. Share-token access is supported for GET receipts only.
4. **`verify_receipt_independent`** lives in `verification.py` so the package stays at six modules as requested.

## Ruff

Targeted `ruff check` / `ruff format` on new governance code passes.
