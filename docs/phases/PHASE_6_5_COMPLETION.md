# Phase 6.5 — Completion Report

## What shipped

- Wave 1 (commit `8c87460`): services, tools, worker primitives (per prior handoff)
- Wave 2 (commit `2d38105`): routers, worker, ReAct loop, WebSocket module, CLI (per prior handoff)
- Wave 3 (commit `e1509a6`): BFF routes, hooks, types, WebSocket client hook, backend WS mount
- Wave 4 (commit `33d5d73`): dashboard pages (vault, definitions, runs), UI components, sidebar links

## Test counts

- Backend: run `cd apps/backend && .venv/bin/python -m pytest tests/ --no-cov -q` with Postgres + Redis (default test Redis port in `conftest`); full suite requires services up.
- Frontend: `cd apps/frontend && npm test -- --run` — 7 Vitest tests passing in CI for this slice.
- SSRF matrix: unchanged worker tests (`tests/workers/test_tools.py`) — run with Redis available.
- Secret-grep after FE tests: `grep -E 'sk-|gsk_|…' /tmp/fe-tests.out` — clean when no secrets in logs.

## EARS clauses (verification notes)

| Clause | Notes |
|--------|--------|
| R1 | Vault UI lists masked keys; add/delete via BFF → `/api/v1/projects/.../vault` |
| R2 | Definitions list/create/archive; forms use `Controller` + `Input` (forwardRef) |
| R3 | Run dialog → POST run + mint ws token → navigate to run detail |
| R4 | Timeline renders streamed JSON events in order |
| R5 | Backend `LRANGE` + reverse in `axiom.workers.websocket` |
| R6 | Results show `final_output.final_text`, receipts, duration, status |
| R7 | BFF maps backend `403` → `404` for project-scoped routes |
| R8 | `parseApiError` + toasts; `401` redirects via BFF or client |
| R9 | BFF sends `Authorization: Bearer` from session cookie |
| R10 | WS `/ws/agent-runs/{id}?token=`; close `4401` on bad JWT/hash |
| R11 | No MCP/templates/schedules added in this diff |
| R12 | `npm run build` green; backend pytest requires Redis for full run |

## Dev-UX follow-up (post–Phase-6.5 tag window)

- **Auto-mint worker API key:** `./axiom dev` can create a dev-scoped AXIOM project API key and persist `AXIOM_WORKER_GATEWAY_API_KEY` in `apps/backend/.env`, removing manual dashboard copy/paste for the agent worker. Split-brain rules are unchanged (worker authenticates to the gateway; vault decryption stays gateway-only). See `docs/dev-setup.md` and `./axiom rotate-worker-key`.

## Known limitations (Phase 6.6+ backlog)

- Richer timeline events (per-tool LLM/tool_result payloads) depend on worker publishing additional event types; current loop emits `react_iteration` plus worker lifecycle events.
- `AgentRunOut` API does not yet expose `total_tokens` / `total_cost_usd` columns — UI shows duration + `final_output` only.
- Multi-project JWT users: backend may return `403` before BFF mapping; membership errors are mapped to `404` only for forwarded project routes.

## Files added (summary)

- Backend: WebSocket route on `main.py`; `GET`/`PATCH` on `agent_definitions` router; `404` for missing definition on `POST /agent-runs`.
- Frontend: `app/api/projects/[projectId]/agent-definitions/**`, `agent-runs/**`, `app/dashboard/projects/[projectId]/**`, `components/{vault,agent-definitions,runs}/**`, hooks, `lib/agent-runner-api.ts`, tests under `__tests__/`.

## Files modified (summary)

- `apps/backend/src/axiom/main.py`, `services/agent_runs.py`, `routers/v1/agent_runs.py`, `schemas/agent_definitions.py`, `routers/v1/agent_definitions.py`, `tests/api/test_agent_runs.py`
- `apps/frontend/components/sidebar.tsx`, `lib/api.ts`, `lib/types.ts`, `lib/dashboard-query-keys.ts`, `components/ui/input.tsx`, `components/auth/auth-text-field.tsx`
