# Phase 9 build prompts

Three sequenced prompts for a coding agent working in this repo. Run them **in
order**, one at a time, committing between each. Each prompt inherits the
"House rules" block below — paste it with every prompt.

Phase 9.0 — Governed knowledge retrieval (RAG as a governed tool)
Phase 9.1 — Reusable governed-action webhook for n8n
Phase 9.2 — Automation value metrics

---

## House rules (paste with every prompt)

You are working in the Grace monorepo (`apps/backend`, `apps/frontend`,
`packages/axiom-sdk`, `docs/`). Read `docs/architecture.md`,
`docs/decisions.md`, and `docs/ANTIPATTERN_LIBRARY.md` before writing code.
Note that `docs/architecture.md` is stale (it describes Phase 1 only) — the
real surface area is in `apps/backend/src/axiom/{services,workers,gateway,mcp}`
and `docs/phases/`. Trust the code over the architecture doc.

Non-negotiable constraints:

1. **Grace governs; Grace does not orchestrate.** `docs/ANTIPATTERN_LIBRARY.md`
   records this as a V1 failure mode: "AXIOM governs tool calls; AXIOM does NOT
   orchestrate them. If a customer wants orchestration, they use
   n8n/Temporal/Zapier and AXIOM sits in the governance call." Do not add a
   scheduler, a workflow state machine, retry-as-orchestration, or a DAG
   runner. If a change starts to look like a workflow engine, stop and ask.

2. **Import-linter contracts are law.** See `.importlinter` (ADR-021). Layers
   are `routers → services → models → core`. Models must not import services,
   routers, or middleware. `axiom.mcp` is a delivery layer peer to routers —
   nothing below it may import it. Verify with:
   `cd apps/backend && uv run lint-imports --config ../../.importlinter`

3. **Embedding work is fail-soft.** Mirror
   `axiom.services.policies._embed_policy_best_effort`: an embedding failure is
   logged via `structlog` and leaves the column NULL. It must never block a
   write and never break governance.

4. **Side effects are scheduled after commit.** Mirror the
   `axiom.services.events.schedule_*` and
   `axiom.services.escalation.schedule_escalation` pattern —
   fire-and-forget, never raises into the request path.

5. **Every externally-visible action goes through governance.** Tools call
   `axiom.workers.tools.base.check_governance` and raise `ToolDenied` on a
   non-allow verdict. Do not add a code path that reaches an external system
   without a receipt.

6. **Config style.** Add settings to `axiom/config.py` as
   `pydantic-settings` fields using `Field(..., validation_alias=AliasChoices(
   "GRACE_<NAME>", "AXIOM_<NAME>"))`, with a docstring comment explaining the
   default. Secrets are `SecretStr`. Update `.env.example`.

7. **Migrations.** Run `uv run alembic heads` first to find the real current
   head — do not assume. Name the file
   `<slug>_phase_9_<n>_<description>.py` following the existing convention in
   `apps/backend/alembic/versions/`.

8. **Every phase ends with an ADR.** Append to `docs/decisions.md` using the
   existing format (`## ADR-0NN — Title`, then **Status** / **Context** /
   **Decision** / **Consequences**, then `---`). Next free number is
   **ADR-031** — verify before writing.

9. **Definition of done**, all must pass from `apps/backend`:
   - `uv run pytest`
   - `uv run ruff check . && uv run ruff format --check .`
   - `uv run mypy src`
   - `uv run lint-imports --config ../../.importlinter`
   - `./axiom test` from the repo root

10. Write tests in the existing layout (`tests/services/`, `tests/workers/`,
    `tests/routers/`, `tests/unit/`). Match the style of neighbouring tests —
    they are the spec.

Ask before deviating. Do not refactor unrelated code.

---

## Phase 9.0 — Governed knowledge retrieval

**Why:** Grace has `pgvector` + a swappable embedding provider, but it only
embeds *policies*. There is no way to ground an agent in a project's own
documents. Add retrieval as a **governed tool** — every retrieval emits a
receipt, so "what did the agent read before it acted?" is answerable from the
audit chain. This is the differentiator: not RAG, but *attributable* RAG.

### Read first

- `axiom/services/embeddings/service.py` — provider protocol, `EMBEDDING_DIM`
  (384), lazy fastembed load, OpenAI fallback
- `axiom/core/embedding_dim.py` — why the constant lives in `core`
- `axiom/models/policy.py` — the `Vector(EMBEDDING_DIM)` column pattern and the
  HNSW index comment
- `axiom/services/policies.py` — `policy_embedding_text`,
  `_embed_policy_best_effort`, and the `cosine_distance` search near line 200
- `alembic/versions/i8j9k0l1m2n3_add_policy_embedding_pgvector.py` — how the
  HNSW index was created
- `axiom/workers/tools/base.py` and `axiom/workers/tools/http_fetch.py` — the
  tool contract

### Build

**Models** — new `axiom/models/knowledge.py`:

- `KnowledgeSource`: `Base, UUIDv7Mixin, TimestampsMixin, SoftDeleteMixin`.
  Columns: `project_id` (FK `projects.id`, CASCADE), `slug` (Text),
  `title` (Text), `kind` (Text — `text` | `url` | `upload`), `uri` (Text,
  nullable), `content_sha256` (Text, nullable), `status` (Text, default
  `pending`), `chunk_count` (Integer, default 0),
  `created_by_user_id` (FK `users.id`, RESTRICT).
  Unique `(project_id, slug)`. Partial index on `(project_id, status)` where
  `deleted_at IS NULL`, mirroring `ix_policies_project_id_is_active_active`.
- `KnowledgeChunk`: `project_id` (denormalised for tenant-scoped queries —
  document why in a comment), `source_id` (FK, CASCADE), `ordinal` (Integer),
  `text` (Text), `token_estimate` (Integer), `chunk_metadata` (JSONB, default
  `'{}'::jsonb`), `embedding` (`Vector(EMBEDDING_DIM)`, nullable).
  Unique `(source_id, ordinal)`.

Import `EMBEDDING_DIM` from `axiom.core.embedding_dim`, **not** from the
embeddings service — contract 1 forbids models importing services.

**Migration** — create both tables plus an HNSW cosine index
(`ix_knowledge_chunks_embedding_hnsw`, `vector_cosine_ops`) matching the
existing policy-embedding migration.

**Service** — new package `axiom/services/knowledge/`:

- `chunking.py` — `chunk_text(text: str, *, target_tokens: int, overlap_tokens:
  int) -> list[str]`. Paragraph-aware splitting with a hard character ceiling;
  pure function, no I/O, fully unit-testable. No new dependency — do not add
  langchain or llama-index.
- `ingest.py` — `ingest_source(session, *, project_id, source_id)`: load the
  source, chunk it, embed via `embed_texts` in batches, insert chunks,
  update `chunk_count` and `status`. Embedding failure is fail-soft per house
  rule 3: chunks are still inserted with `embedding = NULL` and status becomes
  `degraded`, not `failed`. Recompute `content_sha256` and skip re-ingestion
  when unchanged.
- `retrieval.py` — `search_chunks(session, *, project_id, query, top_k,
  min_similarity) -> list[ChunkMatch]`. Use `embed_query`, then
  `KnowledgeChunk.embedding.cosine_distance(vector)` with
  `similarity = 1 - distance`, filtered to the project, `embedding IS NOT
  NULL`, ordered by distance. Return `[]` for a blank query. Copy the
  docstring conventions from `services/policies.py`.
- `__init__.py` — re-export the public surface with `__all__`, matching
  `services/embeddings/__init__.py`.

**Tool** — new `axiom/workers/tools/knowledge_search.py`:

- `KnowledgeSearchTool(BaseTool)` with `name = "knowledge_search"`, a JSON
  schema for `{query, top_k, source_slug?}`.
- `execute` calls `check_governance(ctx=ctx, action_type="knowledge.search",
  target=source_slug or "project:knowledge", parameters={"query": ...,
  "top_k": ...}, risk="low")` **before** retrieving. `ToolDenied` propagates.
- Return `{"receipt_id": ..., "matches": [{"source_slug", "ordinal",
  "similarity", "text"}]}` so the receipt binds to exactly what was read.
- Register it in `axiom/workers/tools/__init__.py` inside `_ensure_registered`
  and add it to `__all__`.

**Router** — new `axiom/routers/v1/knowledge.py`, wired in `main.py` with
`prefix="/v1", tags=["knowledge"]` alongside the other v1 routers:

- `POST /v1/knowledge/sources` — create (text or url kind)
- `POST /v1/knowledge/sources/{source_id}/ingest` — trigger ingestion
- `GET /v1/knowledge/sources` — list, paginated like `list_policies`
- `DELETE /v1/knowledge/sources/{source_id}` — soft delete
- `POST /v1/knowledge/search` — retrieval (this HTTP path is advisory/read-only
  and does **not** need a receipt; the *tool* path does. Document the
  distinction in the docstring, mirroring how `preflight` is advisory while
  `govern` is enforcing.)

Schemas go in `axiom/schemas/knowledge.py`.

**MCP** — expose `knowledge_search` in `axiom/mcp/tools.py` under the existing
`mcp:read` scope. Follow ADR-027: the response leads with a natural-language
summary line, then structured data.

**Settings** — `knowledge_enabled` (bool, default `True`),
`knowledge_chunk_target_tokens` (int, 400), `knowledge_chunk_overlap_tokens`
(int, 60), `knowledge_top_k` (int, 5), `knowledge_min_similarity` (float, 0.3).
Update `.env.example`.

**Tests**

- `tests/services/test_knowledge_chunking.py` — pure chunking: overlap,
  paragraph boundaries, empty input, oversized single paragraph
- `tests/services/test_knowledge_ingest.py` — re-ingest is a no-op when
  `content_sha256` is unchanged; embedding failure yields `degraded` status
  with chunks still present
- `tests/services/test_knowledge_retrieval.py` — project isolation (a chunk in
  project A never returns for project B), `min_similarity` filtering, blank
  query returns `[]`
- `tests/workers/test_knowledge_tool_governance.py` — a deny verdict raises
  `ToolDenied` **and no retrieval happens** (assert the session was never
  queried)
- `tests/routers/test_knowledge_router.py` — auth, tenancy, pagination

**ADR-031** — "Knowledge retrieval is a governed tool, not a platform."
Context: agents need grounding, but ungoverned retrieval breaks the audit
story. Decision: chunks live in Postgres/pgvector reusing `EMBEDDING_DIM=384`
rather than a dedicated vector DB (one datastore, one backup story, tenant
isolation via the same row-level project scoping; revisit above ~10M chunks).
Retrieval through the tool path emits a receipt; the HTTP path is advisory.
Consequences: bounded scale, no new infra, retrieval is replayable from the
audit chain.

---

## Phase 9.1 — Reusable governed-action webhook for n8n

**Why:** the n8n integration today is single-purpose — it exists only to
resolve escalations. Any *other* n8n workflow (finance, ops, sales) that wants
a governed action has no entry point. Generalise the existing HMAC pattern into
one reusable node so a non-engineer can drop "ask Grace" into any workflow.
This is the modularity win: build the surface once, every department reuses it.

### Read first

- `apps/backend/README.md` — the existing n8n escalation flow diagram
- `axiom/services/escalation/{signing,dispatcher,webhook_client}.py`
- `axiom/routers/webhooks.py` — HMAC verification and receipt resolution
- `apps/backend/n8n/escalation-workflow.json`
- `axiom/routers/govern.py` and `axiom/routers/v1/governance.py` — the
  governance path you are exposing
- `tests/test_escalation_callback.py` — the test shape to mirror

### Build

**Endpoint** — `POST /webhooks/n8n/govern-action` in `axiom/routers/webhooks.py`
(same router, same HMAC scheme via `services/escalation/signing.verify_signature`).

Request body (`axiom/schemas/n8n_action.py`):

```
workflow_id: str          # n8n workflow identifier
workflow_run_id: str      # n8n execution id — idempotency key
project_id: UUID
agent_id: str
action_type: str
target: str
parameters: dict
risk: Literal["low","medium","high"] = "medium"
mode: Literal["enforce","advise"] = "enforce"
```

Response: `verdict`, `receipt_id`, `reason`, `verify_url` (built from
`settings.verify_base_url`), and `corrected_parameters` when the verdict is
`correct`.

Behaviour:

- Verify HMAC over the **raw body** before parsing — same order as the existing
  callback handler.
- Use a **separate secret** from the escalation callback:
  `n8n_action_secret: SecretStr | None`, aliases
  `AliasChoices("GRACE_N8N_ACTION_SECRET", "N8N_ACTION_SECRET")`. Different
  trust boundary, different key. Return 503 when unset — do not fall back to
  the escalation secret.
- **Idempotency:** Redis `SETNX` on
  `axiom:n8n:action:{workflow_id}:{workflow_run_id}` holding the receipt id,
  TTL 24h. A replay returns the original receipt verbatim rather than issuing a
  second one — an n8n retry must not create two receipts for one action. Reuse
  `axiom.services.redis_client.get_redis`.
- Delegate to the **existing** governance service. Do not duplicate policy
  evaluation logic in the router; if the shared path does not exist as a
  service function, extract it into `services/governance/` so the HTTP, MCP,
  and webhook surfaces all call the same code (this is exactly the reasoning in
  ADR-026 contract 5).
- On a `hold` verdict, reuse the existing escalation dispatch so the current
  callback flow resolves it. No new hold mechanism.

**Reusable workflow** — `apps/backend/n8n/governed-action-workflow.json`:
a sub-workflow callable from any other n8n workflow. Shape: Execute Workflow
Trigger → Code node computing the HMAC signature → HTTP Request to
`/webhooks/n8n/govern-action` → Switch on `verdict` with four branches
(`allow` → return, `correct` → return corrected params, `deny` → throw with the
reason, `hold` → Wait node). Include a `README` note in
`apps/backend/n8n/README.md` on importing it and wiring the secret.

**docker-compose** — add `N8N_ACTION_SECRET` to the existing `n8n` service env
block next to `N8N_CALLBACK_SECRET`.

**Docs** — extend the n8n section of `apps/backend/README.md` with a second
diagram (n8n → Grace → verdict) and a short "which endpoint do I use" table:
`/v1/governance/govern` for code, `/webhooks/n8n/govern-action` for workflows,
`/v1/preflight` for advisory checks.

**Explicit non-goals** — state these in the module docstring: Grace does not
schedule these calls, does not retain workflow state beyond the idempotency
key, and does not retry on the workflow's behalf. n8n owns orchestration.

**Tests** — `tests/test_n8n_action_webhook.py`, mirroring
`tests/test_escalation_callback.py`: valid HMAC → verdict; tampered body → 401;
missing secret → 503; replayed `workflow_run_id` → identical `receipt_id` and
exactly one receipt row; `deny` verdict shape; `hold` triggers escalation
dispatch.

**ADR-032** — "One governed-action surface for external orchestrators."
Context: the escalation callback proved the HMAC machine-caller pattern but was
purpose-built. Decision: generalise it, separate secret, Redis idempotency on
the orchestrator's run id, shared governance service across HTTP/MCP/webhook.
Consequences: any n8n/Zapier/Temporal workflow becomes governable without
backend changes; Grace stays out of orchestration.

---

## Phase 9.2 — Automation value metrics

**Why:** Grace can prove an action was governed but cannot answer "what is this
worth?" `command_center/aggregates.py` already computes posture, policy
breakdown, and crypto health; `AgentRun` already carries `total_tokens` and
`total_cost_usd`. Add the value layer — and make the assumptions auditable
rather than hidden, which is the honest version of an ROI dashboard.

### Read first

- `axiom/services/command_center/aggregates.py` — the `_WINDOW_RE` parsing and
  aggregate query style
- `axiom/schemas/command_center.py` — `PostureOut`, `PolicyBreakdownOut`
- `axiom/routers/v1/command_center.py`
- `axiom/models/agent_run.py` — `total_tokens`, `total_cost_usd`,
  `started_at`, `completed_at`, `status`
- `axiom/models/governance.py` — `GovernanceReceipt`, `GovernanceVerdict`

### Build

**Service** — add to `axiom/services/command_center/aggregates.py` (do not
create a parallel module):

`automation_value(session, *, project_id, window) -> AutomationValue` returning,
for the window:

- `runs_completed`, `runs_failed`, `median_run_seconds`
  (from `completed_at - started_at`)
- `actions_governed`, `actions_allowed`, `actions_corrected`,
  `actions_denied`, `actions_held`
- `tokens_total`, `cost_usd_total` (sum the existing columns; `Decimal`, never
  float)
- `estimated_minutes_saved` and `estimated_hours_saved`
- `assumptions`: the exact multiplier map used, echoed back

**Assumption handling — this is the important part.** Minutes-saved is an
estimate, not a measurement. Therefore:

- The per-action-type multiplier map is a **setting**, not a hardcoded
  constant: `automation_value_minutes_per_action` (JSON string parsed into
  `dict[str, float]`, default `{}`), plus
  `automation_value_default_minutes_per_action` (float, default `0.0`).
- **Default to zero.** With no configured assumptions the endpoint reports
  `estimated_minutes_saved = 0` and an empty `assumptions` map. Grace never
  invents a number.
- Every response echoes the assumption map and an
  `is_estimate: true` flag. A number whose provenance isn't in the payload does
  not ship.
- Reuse the existing `_WINDOW_RE` window parsing (`24h`, `30d`) — do not add a
  second date-parsing scheme.

**Schema** — `AutomationValueOut` in `axiom/schemas/command_center.py`, with
field descriptions that state the estimate caveat (they surface in OpenAPI).

**Router** — `GET /v1/command-center/value?window=30d` in
`axiom/routers/v1/command_center.py`, same auth and project scoping as the
sibling endpoints.

**Frontend** — add a card to the existing Command Center page
(`apps/frontend`, Next.js 14 App Router, TanStack Query — follow the fetching
pattern of the adjacent posture card). Render hours saved with a visible
"estimate — based on your configured assumptions" affordance and a tooltip
listing the multiplier map. If assumptions are empty, render an empty state
inviting configuration rather than a zero.

**Settings** — the two fields above, with a `field_validator` parsing the JSON
map (mirror the existing `backend_cors_origins` validator style). Update
`.env.example`.

**Tests** — `tests/services/test_automation_value.py`: window parsing,
`Decimal` cost summation with no float drift, project isolation, empty
assumptions ⇒ zero minutes and empty map, configured assumptions ⇒ correct
arithmetic, malformed assumption JSON ⇒ validation error at settings load, not
at request time.

**ADR-033** — "Value metrics are estimates with declared assumptions."
Context: ROI dashboards usually hide their multipliers, which is
indefensible in a product whose thesis is auditability. Decision: multipliers
are configuration, default to zero, and every response echoes the assumptions
that produced the number. Consequences: the figure is defensible in a review;
the cost is that the dashboard is empty until someone commits to an
assumption — which is the correct default.

---

## Suggested sequencing

Phase 9.1 is the smallest and highest-leverage — it reuses machinery that
already works and produces something demonstrable in a day or two. Phase 9.0 is
the largest and the one that most changes what Grace can claim. Phase 9.2 is
cosmetic without the other two but is what makes the work legible to a
non-technical stakeholder.

If you only run one: run **9.1**.
