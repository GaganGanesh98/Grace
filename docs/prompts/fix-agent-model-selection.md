# Fix prompt: provider-aware model selection in the project workspace

Paste this into Claude Code at the repo root.

---

There are two agent-creation UIs in this repo and the wrong one is wired to the
"+ NEW AGENT" button in the project workspace. Fix that, then close the gaps the
provider registry still has.

## Task 1 — kill the duplicate hardcoded model list (the actual bug)

`apps/frontend/components/project-workspace/project-workspace-tabs-extra.tsx`
declares a module-level `const MODELS = [...]` with six hardcoded ids
(`gpt-4o`, `claude-3-5-sonnet-20241022`, ...) and renders it as a flat `<select>`
in `NewAgentModal`. This list is stale, is not filtered by the selected vault
credential, and ignores `GET /api/v1/providers`, which already exists and already
serves the registry.

`apps/frontend/components/agent-definitions/agent-form.tsx` already does this
correctly: it takes `providers: LlmProvider[]`, derives `modelOptions` from the
provider matching the selected vault key's `service`, resets the model when the
credential changes, offers a `Custom model…` free-text escape hatch, and blocks
submit on a `provider/model` prefix mismatch.

Do this:

1. Delete the `MODELS` constant and the whole hand-rolled `NewAgentModal` body in
   `project-workspace-tabs-extra.tsx`.
2. Re-implement `NewAgentModal` as a thin dialog wrapper around `<AgentForm />`,
   the same way `components/agent-definitions/agent-create-panel.tsx` does it —
   fetch providers with `fetchLlmProviders()` via TanStack Query
   (`dashboardKeys.llmProviders`), fetch vault keys with `listVaultKeys({ kind: "llm" })`,
   pass both down, keep the existing `onSuccess` cache invalidations and the
   `toast.success("Agent created")`.
3. Keep the `Hard enforcement` checkbox behaviour if `AgentForm` doesn't cover it —
   add it to `AgentForm` as an optional prop rather than forking the component again.
4. Delete `apps/frontend/__tests__/components/agent-definitions/agent-form.test.tsx`
   assertions that depend on the old flat list only if they actually break; prefer
   updating them. Add a test asserting that selecting a Groq vault key shows Groq
   models and does **not** show `gpt-4o`.

Acceptance: with only a `gsk_`-prefixed Groq key in the vault, the model dropdown
in the project workspace shows Groq models plus `Custom model…`, and shows no
OpenAI/Anthropic/Google ids.

## Task 2 — expand the Groq model list in the registry

`apps/backend/src/axiom/gateway/provider_registry.py` lists only three Groq models.
Groq serves considerably more. Fetch the current list from
`https://api.groq.com/openai/v1/models` (or the Groq docs) and update the `models`
tuple for the `groq` entry with the currently-served production models. Do the same
sanity pass for `openai`, `anthropic`, and `google`. Keep `default_model` pointing at
a model that is actually in the tuple.

Note the curated tuples are deliberately non-exhaustive — the `Custom model…` path in
`AgentForm` is the escape hatch, so do not attempt to enumerate every id. But the
registry list should not be so short that it looks broken.

## Task 3 — fix the hardcoded Gemini path

`apps/backend/src/axiom/workers/gateway_routes.py::gateway_llm_post_path` returns
`"models/gemini-pro:generateContent"` for the `google` provider regardless of which
model the agent definition selected. Any Google agent therefore silently calls
`gemini-pro`. Thread the model id through and build the path from it, matching
`ProviderSpec.chat_path`'s `{model}` placeholder. Add a unit test.

## Task 4 — make run failures diagnosable from the workspace

`AgentRun.error_message` is persisted by `workers/agent_worker.py` and exposed by
`AgentRunOut`, but the project workspace "Recent runs" table renders only a `FAILED`
badge with no reason and no link. Only `components/runs/results-view.tsx` surfaces it.

Make each row in the Recent runs table and the Runs tab link to the run detail view,
and show a truncated `error_message` inline on failed rows with the full text on hover
(`title` attribute).

## Task 5 — label the placeholder metrics honestly

These are hardcoded placeholders, not computed values, and they read as if the feature
is broken:

- `components/project-workspace/project-tab-panels.tsx` — `COST (MTD)` renders `—` with
  subtext "your LLM provider bills"; `GOVERNANCE BLOCKS` renders `—` with
  "governance denials are not yet attributed per run in the API".
- `project-workspace-tabs-extra.tsx` — agent cards render
  "(stats require backend aggregates)".

Either implement the aggregates or replace the em-dash with an explicit
`Not tracked yet` state so it is clear the number is unimplemented rather than zero.
Pick one and say which in the PR description. Do not leave bare `—`.

## Constraints

- `pytest`, `ruff`, and `mypy` are already red at HEAD. Capture the baseline
  before you start and diff against it — do not attribute pre-existing failures
  to these changes.
- Do not add a second copy of the model list anywhere. The provider registry is
  the single source of truth; the frontend reads it over `/api/v1/providers`.
