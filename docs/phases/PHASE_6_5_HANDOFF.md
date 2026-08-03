# Phase 6.5 — Handoff Checkpoint

**Context:** Session paused at ~55% to avoid context degradation. This document captures state as of the handoff save so work can continue in a **fresh Cursor chat** without re-deriving decisions or file lists.

**Phase:** 6.5 — Agent definitions, runs, worker, tools, WebSocket (dashboard-triggered execution with governance).

---

## 1. Exact current state

### Wave / batch overview

| Wave | Scope | Status |
|------|--------|--------|
| **Recon** | Provider fabric + legacy agents router disposition | **Done** (evidence in prior session; no separate doc in repo beyond this handoff) |
| **Batch A** | Migrations, SQLAlchemy models, RED tests, Phase 6.7 backlog note | **Done** (initial implementation) |
| **Batch A corrections** | Seven follow-up schema/model fixes (see §3) | **Not applied** in tree — still pending |
| **Batch B** | Routers, services, worker, tools, WebSocket, BFF, frontend | **Not started** |

### Sub-tasks checklist

- [x] Recon: Tensions 1–3 decisions recorded (see §2)
- [x] Alembic: `agent_definitions` migration (`f8c1d2e3a4b5`)
- [x] Alembic: `agent_runs` migration (`f9c1d2e3a4b6`)
- [ ] Alembic: amendment migration `f9c1d2e3a4b7` (and related column renames / new fields) — **not present**
- [x] Models: `AgentDefinition`, `AgentRun` (+ `AgentRunStatus` enum)
- [x] `axiom.models.__init__` exports updated
- [ ] Routers `/v1/agent-definitions`, `/v1/agent-runs` — **not implemented**
- [ ] Dual auth dependency `require_api_key_or_current_user` (or equivalent) — **not wired**
- [ ] Services: definition CRUD, auto-create legacy `agents` row, run queue — **not implemented**
- [ ] Package `axiom.workers` — **does not exist**
- [x] RED tests under `tests/api/` and `tests/workers/` (expect 404 / missing modules)
- [x] `docs/phases/PHASE_6_7_BACKLOG.md` created
- [ ] Migrations **not** applied to developer DB (user asked to review diffs first; state may still be pre–Batch A tables unless someone ran Alembic locally)

### File-by-file (Batch A deliverables)

| File | Role | Status |
|------|------|--------|
| `apps/backend/alembic/versions/f8c1d2e3a4b5_phase_6_5_agent_definitions.py` | Create `agent_definitions` | Done; `model` column **512** chars (correction to 1024 **not** applied) |
| `apps/backend/alembic/versions/f9c1d2e3a4b6_phase_6_5_agent_runs.py` | Create `agent_runs` | Done; still has `output_payload`; no extra metrics columns |
| `apps/backend/src/axiom/models/agent_definition.py` | ORM `AgentDefinition` | Done; `String(512)` for `model` |
| `apps/backend/src/axiom/models/agent_run.py` | ORM `AgentRun` | Done; maps `output_payload` |
| `apps/backend/src/axiom/models/__init__.py` | Exports | Updated |
| `apps/backend/tests/api/test_agent_definitions.py` | RED API tests | Present; fails until routes exist |
| `apps/backend/tests/api/test_agent_runs.py` | RED API tests | Present |
| `apps/backend/tests/workers/test_*.py` | RED worker imports | Present (expect `axiom.workers` missing) |
| `apps/backend/tests/test_agents.py` | Legacy JWT agents CRUD | **Unchanged**; should stay green |
| `docs/phases/PHASE_6_7_BACKLOG.md` | 6.7 deferrals | Done |

---

## 2. Architectural decisions locked

### Tension 1 — Provider fabric (Phase 6.5 scope)

- **Do not** unify vault / gateway / routes in 6.5; that is **Phase 6.7 — Provider Fabric Unification**.
- **Worker gateway base:** `http://localhost:8001/v1/{provider}/...` using vault key’s resolved provider.
- **Supported providers for the agent runner in 6.5:** `openai`, `anthropic`, `google`, `groq`, `xai` (the five first-class gateway routes in `gateway/app.py`).
- If `vault_key.provider` is `replicate`, `together`, `cohere`, `mistral`, or `custom`, **creation must return HTTP 400** with a clear message listing supported providers and referencing Phase 6.7.
- **Do not** route worker traffic through `/v1/proxy/...` for credential injection (unsafe as implemented).

### Tension 2 — Legacy agents vs new definitions

- **Keep** existing `/api/v1/projects/{project_id}/agents` router and **`agents` table** — no delete/rename in 6.5.
- New resource: **`agent_definitions`** table, FK to **`agents.id`** (required) and **`vault_keys.id`**, plus `project_id`, `created_by`, etc.
- **`agent_runs`** FK → **`agent_definitions.id`** (not to legacy `agents` directly).
- On **create** of an `agent_definition` via the new API: **auto-create** a matching row in **`agents`** via existing agent service if no matching slug exists in the project (preserves integrity with `executions.agent_id` and governance fixtures).
- New HTTP surface: **`/v1/agent-definitions`** and **`/v1/agent-runs`** (dual auth). Phase 6.5 **frontend** talks only to these; **no** new UI for legacy agents routes.

### Tension 3 — `/govern` auth

- **`/v1/governance/govern`** remains **API-key-only**.
- Dashboard runs use a **server-side project API key** (BFF; auto-create “dashboard runner” key per project as specified); **frontend never sees** raw API keys.

---

## 3. Seven Batch A corrections — applied?

These were identified **after** the initial Batch A land; **verify against repo** before Batch B.

| # | Correction | Applied? | Evidence / notes |
|---|------------|----------|------------------|
| 1 | `agent_definitions.model` **512 → 1024** | **No** | Migration + model still `String(512)` / `length=512` |
| 2 | Standalone index **`ix_agent_runs_status`** on `agent_runs.status` | **No** | Only composite `ix_agent_runs_project_status_created` + others; no standalone `status` index |
| 3 | Add **`total_tokens`**, **`total_cost_usd`**, **`last_heartbeat_at`**, **`receipt_ids`** (shape TBD) | **No** | Not in `f9c1d2e3a4b6` or `agent_run.py` |
| 4 | Rename **`output_payload` → `final_output`** | **No** | Column still `output_payload` in migration and model |
| 5 | New amendment migration **`f9c1d2e3a4b7`** | **No** | File not present under `alembic/versions/` |
| 6 | Update **`agent_run.py`** to match amended schema | **No** | Model matches original Batch A only |
| 7 | Confirm **`tests/test_agents.py`** still passing | **Yes** | `pytest tests/test_agents.py --no-cov` → **1 passed** (run at handoff time) |

**Next coding session should likely apply corrections 1–6 (or explicitly supersede them) before building Batch B on top of schema.**

---

## 4. Batch B — suggested four waves

Work can overlap **within** a wave where files do not conflict; **across** waves, respect dependencies.

| Wave | Contents | Parallel-safe notes |
|------|----------|---------------------|
| **B1 — Schema finish** | Apply Batch A corrections: amendment migration `f9c1d2e3a4b7` (or superseding revision), align `agent_definition` / `agent_run` models, regenerate/adjust RED tests if column names change | Sequential with DB review; avoid parallel edits to same migration file |
| **B2 — API core** | Dual-auth deps, Pydantic schemas, services (definitions CRUD + auto `agents` row, vault provider validation), register **`/v1/agent-definitions`** and **`/v1/agent-runs`** (CRUD, cancel, ws-token stub), flip **`tests/api/**`** green | Routers + services in same wave; parallel possible if one owns schemas/deps and another owns routers after interfaces fixed |
| **B3 — Worker runtime** | Create **`axiom.workers`** package: gateway client (Bearer project API key + `X-Axiom-Agent-ID`), ReAct loop, tool dispatch, job processor; **`tests/workers/**`** green | Can split worker files in parallel once module layout agreed |
| **B4 — Realtime + dashboard** | WebSocket or SSE contract, BFF routes, dashboard UI, “dashboard runner” API key behavior, integration tests | BFF/frontend can lag API if API stable; WebSocket depends on run lifecycle from B3 |

---

## 5. Disciplines to keep

- **Controller / service layering:** Thin routers; business logic in services; shared validation in one place (especially vault provider allowlist).
- **Gateway routing:** Worker only uses **named** `/v1/{openai|anthropic|google|groq|xai}/...` paths for LLM calls; no generic proxy for secrets.
- **Receipts / governance:** Preserve **receipt on every governed gateway call** semantics; align `X-Axiom-Agent-ID` with classifier expectations.
- **SSRF / network:** Any outbound URL handling must stay aligned with existing **`assert_public_http_url`** / policy patterns; do not weaken gateway SSRF guards in 6.5.
- **Logging:** **No secrets** (API keys, raw vault material) in logs or error payloads.
- **Legacy tables:** **Do not** alter **`agents`** or **`executions`** schema beyond additive FK-safe usage; legacy **`/api/v1/projects/.../agents`** stays.

---

## 6. Phase 6.7 backlog carryover

Documented in **`docs/phases/PHASE_6_7_BACKLOG.md`**. Summary:

- **`classifier.py`:** `p != "custom"` vs `PROVIDERS` — latent logic; fix in 6.7 with provider fabric work.
- **Three-mechanism mismatch:** `PROVIDER_PATTERNS` / `PROVIDERS` / gateway routes alignment.
- **`generic_proxy`:** strips `Authorization`, no `inject_credentials` — unsafe for vault-backed arbitrary URLs until 6.7.

---

## 7. Files touched so far (Phase 6.5 Batch A + docs)

```
apps/backend/alembic/versions/f8c1d2e3a4b5_phase_6_5_agent_definitions.py
apps/backend/alembic/versions/f9c1d2e3a4b6_phase_6_5_agent_runs.py
apps/backend/src/axiom/models/agent_definition.py
apps/backend/src/axiom/models/agent_run.py
apps/backend/src/axiom/models/__init__.py
apps/backend/tests/api/__init__.py
apps/backend/tests/api/test_agent_definitions.py
apps/backend/tests/api/test_agent_runs.py
apps/backend/tests/workers/__init__.py
apps/backend/tests/workers/test_agent_worker.py
apps/backend/tests/workers/test_react_loop.py
apps/backend/tests/workers/test_tools.py
apps/backend/tests/workers/test_websocket.py
docs/phases/PHASE_6_7_BACKLOG.md
docs/phases/PHASE_6_5_HANDOFF.md
```

*Legacy `tests/test_agents.py` intentionally **not** modified.*

---

## 8. Tests — passing / failing

| Test path | Classification | Notes |
|-----------|----------------|--------|
| `tests/test_agents.py` | **Passing** | Legacy agents API; run with `--no-cov` if using subset |
| `tests/api/test_agent_definitions.py` | **Failing (RED)** | Expect `/v1/agent-definitions` → **404** until Batch B |
| `tests/api/test_agent_runs.py` | **Failing (RED)** | Expect `/v1/agent-runs` routes → **404** |
| `tests/workers/test_*.py` (4 files) | **Failing (RED)** | `axiom.workers` package missing; `pytest.fail` / import path |

**Tip:** For partial runs, use `pytest --no-cov` — repo `addopts` enforces **80%** coverage and fails when only a subset runs.

---

## 9. Next action — paste into a fresh Cursor chat

Use this prompt to resume **from this checkpoint** (after optional local DB migration review):

```
Continue Phase 6.5 from the handoff checkpoint.

Read docs/phases/PHASE_6_5_HANDOFF.md in full — it is authoritative for current state.

Priority before Batch B API/worker code:
1) Apply the seven Batch A corrections listed in §3 of that doc (512→1024 model field, ix_agent_runs_status, total_tokens/total_cost_usd/last_heartbeat_at/receipt_ids, output_payload→final_output, new amendment migration f9c1d2e3a4b7, align agent_run.py). Confirm tests/test_agents.py still passes.
2) Then implement Batch B per §4 waves: dual-auth /v1/agent-definitions and /v1/agent-runs, services (auto-create agents row, 400 for unsupported vault providers), axiom.workers, WebSocket/BFF as spec’d.

Locked decisions: §2 of PHASE_6_5_HANDOFF.md. Do not touch legacy agents table/router beyond additive behavior. Phase 6.7 items stay out of scope (see PHASE_6_7_BACKLOG.md).

Start with schema corrections + migrations, then routers/services, then workers. Show diffs and test results before large UI work.
```

---

*End of handoff.*
