# Phase 6.5 — Wave 2 Handoff Checkpoint

**Purpose:** Fresh-chat resume after Wave 1 landed. Wave 2 = API surface, worker runtime (ReAct + job processor), WebSocket handler, CLI wiring.

---

## 1. Exact state

| Item | Status |
|------|--------|
| **Batch A** (migrations + models + amendment `f9c1d2e3a4b7`) | Committed earlier in Phase 6.5 (separate commit chain) |
| **Batch B — Wave 1** (services, `axiom.workers` tools, tests) | **Committed** — see repo history |
| **Wave 1 commit SHA** | `8c87460` |
| **Wave 2** | **Pending** — routers, schemas, deps, `agent_worker`, `react_loop`, WebSocket, mounts |

---

## 2. What’s green (passing tests + counts)

Run with DB migrated through `f9c1d2e3a4b7` and Redis available (see `tests/conftest.py` env defaults).

| Suite | Count | Notes |
|-------|------:|--------|
| `tests/services/test_agent_definitions_service.py` | **3** | Legacy-agent bridge + replicate 400 |
| `tests/workers/test_tools.py` | **13** | Registry, SSRF matrix, redirect, file write, web search disabled |
| `tests/test_agents.py` | **1** | Legacy JWT agents CRUD — **no regression** |
| **Total (Wave 1 green)** | **17** | |

---

## 3. What’s still RED (needs Wave 2+)

| Path | Why |
|------|-----|
| `tests/api/test_agent_definitions.py` | **3** tests — `/v1/agent-definitions` not registered → **404** |
| `tests/api/test_agent_runs.py` | **4** tests — `/v1/agent-runs` not registered → **404** |
| `tests/workers/test_agent_worker.py` | Missing `axiom.workers.agent_worker` (`process_run` or `run_agent_job`) |
| `tests/workers/test_react_loop.py` | Missing `axiom.workers.react_loop` (`run_react_loop` or `run`) |
| `tests/workers/test_websocket.py` | Missing `axiom.workers.websocket` (`handle_run_stream` or `stream_handler`) |

`tests/workers/test_tools.py` is **GREEN** — do not break.

---

## 4. Locked decisions (Tensions 1–3)

### Tension 1 — Provider fabric (Phase 6.5 scope)

- **Do not** unify vault / gateway / routes in 6.5; **Phase 6.7 — Provider Fabric Unification**.
- **Worker gateway base:** `http://localhost:8001/v1/{provider}/...` using the vault key’s resolved **provider** (from `vault_keys.provider` / detection).
- **Supported providers for the agent runner in 6.5:** `openai`, `anthropic`, `google`, `groq`, `xai` (first-class gateway routes).
- Unsupported providers (`replicate`, `together`, `cohere`, `mistral`, `custom`, …): **HTTP 400** on **agent definition create** with message referencing Phase 6.7 (implemented in `AgentDefinitionService`).
- **Do not** route worker LLM traffic through `/v1/proxy/...` for credential injection.

### Tension 2 — Legacy agents vs definitions

- Keep **`/api/v1/projects/{project_id}/agents`** and **`agents` table** — no delete/rename in 6.5.
- **`agent_definitions`** FK → **`agents.id`** + **`vault_keys.id`**; **`agent_runs`** FK → **`agent_definitions.id`**.
- **Create** definition: auto-create legacy **`agents`** row if no `(project_id, slugify(name))` match (Wave 1 service).
- New HTTP: **`/v1/agent-definitions`**, **`/v1/agent-runs`** (dual auth). Frontend uses these only for new UI.

### Tension 3 — Governance auth

- **`POST /v1/governance/govern`** is **API-key-only** (not session-JWT for govern body in engine).
- Dashboard: **server-side project API key** (BFF); frontend never sees raw keys.

---

## 5. Wave 1 audit — three must-fixes (all applied before Wave 1 commit)

1. **`correlation_id` = UUIDv7** — `axiom.utils.ids.new_uuidv7_str()` via **`uuid6`** (`uuid7()`), not `uuid4()`. (`apps/backend/src/axiom/services/agent_runs.py`)
2. **Governance URL** — Verified **`/v1/governance/govern`** matches `main.py` mount `prefix="/v1/governance"` + `@router.post("/govern")`. **`check_governance`** in `workers/tools/base.py` unchanged and correct (no `/api` prefix).
3. **Service tests** — `tests/services/test_agent_definitions_service.py` (3 tests): auto-create agent, reuse agent, replicate → 400 with exact message.

---

## 6. Disciplines (reaffirm)

- **FieldControl banned** — controller/service layering only.
- **Gateway routing:** worker uses **named** `/v1/{openai|anthropic|google|groq|xai}/...` on port **8001**; no generic proxy for secrets.
- **Receipts / governance:** receipt on every governed gateway call; align **`X-Axiom-Agent-ID`** with classifier expectations.
- **SSRF:** tool HTTP fetch remains the hard bar (tests in `test_tools.py`).
- **Logging:** no API keys or vault material in logs or error payloads.
- **Legacy:** do not alter **`agents`** / **`executions`** schema except additive FK-safe usage; legacy agents router stays.

---

## 7. Wave 2 — file list (indicative)

- **Routers:** `apps/backend/src/axiom/routers/v1/agent_definitions.py`, `agent_runs.py` (or single module split by resource) — thin handlers.
- **Schemas:** Pydantic request/response models under `apps/backend/src/axiom/schemas/` (agent definitions / runs).
- **Deps:** dual auth `require_api_key_or_current_user` (or equivalent) wired for `/v1/agent-definitions`, `/v1/agent-runs`.
- **Registration:** **`apps/backend/src/axiom/main.py`** — this repo has **no** `axiom/api/__init__.py`; routers are **`include_router(..., prefix=...)`** on the FastAPI `app` (follow **`/v1/governance`** pattern: e.g. `prefix="/v1"` with paths `agent-definitions`, `agent-runs`).
- **Worker:** `apps/backend/src/axiom/workers/agent_worker.py` — job consumer (Redis queue `axiom:agent_runs:pending`), calls services + gateway client.
- **ReAct:** `apps/backend/src/axiom/workers/react_loop.py` — multi-step loop, tool dispatch via `dispatch_tool`.
- **WebSocket:** `apps/backend/src/axiom/workers/websocket.py` (or `axiom/routers/websocket` + worker helpers) — validate **5‑min JWT** against `ws_token_hash`, stream events from Redis pub/sub / logs.
- **CLI / entrypoint:** worker process command (e.g. `axiom-worker` or `python -m axiom.workers...`) as spec’d in repo conventions.

---

## 8. Wave 2 — test targets (must go GREEN)

| Target | Tests |
|--------|------:|
| API | `tests/api/test_agent_definitions.py` — **3** |
| API | `tests/api/test_agent_runs.py` — **4** |
| Worker | `tests/workers/test_agent_worker.py` — **1** |
| Worker | `tests/workers/test_react_loop.py` — **1** |
| Worker | `tests/workers/test_websocket.py` — **1** |
| Regression | `tests/workers/test_tools.py` — **13** (stay green) |
| Regression | `tests/services/test_agent_definitions_service.py` — **3** |
| Regression | `tests/test_agents.py` — **1** |

---

## 9. Specific things to watch for in Wave 2

- **Gateway:** Worker calls **`http://localhost:8001/v1/{provider}/{path}`** where **`provider`** comes from **`vault_keys.provider`** (after resolution); Bearer = **project API key**; never call OpenAI/Anthropic URLs directly from worker with raw vault secrets outside gateway.
- **ReAct / governance:** On tool governance **denial**, feed **observations** back into the LLM context — **do not** raise uncaught exceptions that kill the loop unless the test contract requires it.
- **WebSocket token:** **5‑minute JWT** scoped to **`run_id`**; store only **hash** in `ws_token_hash`; WS handler validates JWT + run lifecycle.
- **Router mounts:** Register in **`main.py`** with the same **`/v1/...`** style as existing governance routes (no fictional `axiom/api` package in this tree).
- **WebSocket mount:** Add route in **`main.py`** (or dedicated router included there) — e.g. `app.add_api_route` / `APIRouter` WebSocket path aligned with run resource.

---

## 10. Next action — paste into a fresh Cursor chat

```
Continue Phase 6.5 Wave 2 from docs/phases/PHASE_6_5_WAVE2_HANDOFF.md (authoritative).

Wave 1 is committed (SHA in doc). Implement:
- /v1/agent-definitions and /v1/agent-runs routers + Pydantic schemas + dual-auth deps; wire AgentDefinitionService and AgentRunService; flip tests/api/* green.
- axiom.workers.agent_worker (queue consumer), react_loop (ReAct; governance denials as observations), websocket handler (JWT validation for run_id).
- Register routers and WebSocket in axiom/main.py (no axiom/api package — use include_router / app patterns like /v1/governance).

Keep: gateway at localhost:8001 named provider paths; SSRF/tool tests green; legacy agents table/router unchanged; no secrets in logs.

Run: pytest tests/api/ tests/workers/ tests/services/test_agent_definitions_service.py tests/test_agents.py -v --no-cov

Do not implement Phase 6.7 backlog items.
```

---

## 11. Phase 6.7 backlog carryover

See **`docs/phases/PHASE_6_7_BACKLOG.md`**.

- **`classifier.py`:** `p != "custom"` vs `PROVIDERS` — latent logic; fix with provider fabric.
- **Three-mechanism mismatch:** `PROVIDER_PATTERNS` / `PROVIDERS` / gateway routes alignment.
- **`generic_proxy`:** strips `Authorization`, no `inject_credentials` — unsafe until 6.7.

**Dev noise (not 6.7 scope):** passlib/bcrypt may log a trapped warning during tests (`bcrypt` `__about__` attribute) — cosmetic; do not mistake for a secrets leak.

---

*End of Wave 2 handoff.*
