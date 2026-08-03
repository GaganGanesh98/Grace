# Phase 6.6 — Backlog (carryover from Phase 6.5 closeout)

Items observed while finishing the agent-runner dashboard slice.

## Worker event stream

- Emit structured events for each LLM request, tool invocation, and tool result (for timeline parity with EARS “live trace” wording) instead of relying primarily on `react_iteration` and lifecycle events.

## API surface

- Expose `total_tokens` and `total_cost_usd` on `AgentRunOut` when populated so the run results view can show token/cost totals without scraping `final_output`.

## BFF / auth edge cases

- Consider normalizing all cross-project failures to `404` in the backend for JWT sessions (not only in BFF) so behavior is consistent if clients call the API directly.

## UI

- Virtualize the execution timeline for runs with very large event counts (500+).
- Artifact download links when artifacts are exposed via HTTP (currently paths are best-effort from `final_output` if present).
