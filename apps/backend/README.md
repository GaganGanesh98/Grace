# AXIOM backend

FastAPI service. Run with `uv run uvicorn axiom.main:app --reload --host 0.0.0.0 --port 8000` from this directory.

## n8n escalation flow

When the governance engine **holds/escalates** an agent action (a high-risk
action that needs a decision), Axiom fires a real n8n workflow to handle
notification + escalation, and n8n calls back with the decision — instead of
that hold just sitting in a table.

### End-to-end

```
agent action ──> govern engine ──(verdict = hold)──> pending receipt
                                        │
                     schedule_escalation (fire-and-forget, post-commit)
                                        │
                                        ▼
        POST N8N_ESCALATION_WEBHOOK_URL  (signed payload)
        { agent_id, action, policy_violated, severity, timestamp,
          link, callback_url, receipt_id }
                                        │
                                   n8n workflow
                          (notify Slack/email → decide)
                                        │
        POST /webhooks/n8n/escalation-result   (HMAC-signed)
        { receipt_id, decision, reason }
                                        │
                                        ▼
        verify X-Axiom-Signature → resolve the pending receipt:
          approved → verdict=allow + seal
          rejected → verdict=deny + seal
          escalated_to_human → leave pending for a human
```

**Design notes (for a walkthrough):**
- **Trigger** is co-located with the existing `approval.created` event, in
  non-frozen code — the signed-receipt pipeline is untouched.
- **Outbound** (`services/escalation/`) is fire-and-forget with bounded
  exponential backoff + jitter (`httpx`, no retry library) and is **fail-soft**:
  if n8n is down, governance is unaffected. Off unless `ESCALATION_ENABLED=1`.
- **Callback** (`POST /webhooks/n8n/escalation-result`) is authenticated by
  **HMAC-SHA256 over the raw body** (`X-Axiom-Signature: sha256=…`,
  `hmac.compare_digest`) — a bad/missing signature is `401`, no secret configured
  is `503`. It reuses the **existing** hold-resolution path to seal the receipt;
  no parallel status logic, no new table.

### Config

```bash
ESCALATION_ENABLED=1
N8N_ESCALATION_WEBHOOK_URL=http://localhost:5678/webhook/axiom-escalation
N8N_CALLBACK_SECRET=dev_escalation_secret_change_me   # shared with n8n
```

### Run it locally

```bash
# 1. Start Postgres + Redis + n8n
docker compose up -d postgres redis n8n
uv run alembic upgrade head

# 2. In n8n (http://localhost:5678): import n8n/escalation-workflow.json and
#    Activate it. Ensure N8N_CALLBACK_SECRET matches the backend's.

# 3. Start the API with escalation enabled
ESCALATION_ENABLED=1 \
N8N_ESCALATION_WEBHOOK_URL=http://localhost:5678/webhook/axiom-escalation \
N8N_CALLBACK_SECRET=dev_escalation_secret_change_me \
uv run uvicorn axiom.main:app --reload --port 8000

# 4. Trigger a hold (high-risk action) via POST /v1/governance/govern.
#    Axiom → n8n → callback → the receipt is auto-approved and sealed.
```

The sample workflow (`n8n/escalation-workflow.json`) is Webhook → a Code node
(demo notify + auto-approve, signs the callback with the shared secret) → HTTP
Request back to Axiom. Swap the Code node for a Slack/email node + a real
decision branch as needed.

**Tests:** `tests/test_escalation_webhook_client.py` (retry/backoff: success,
5xx-then-success, give-up, no-retry-on-4xx, network-error-then-success; HMAC
sign/verify) and `tests/test_escalation_callback.py` (approve/reject/escalate
resolution, and the failure cases — missing signature → 401, invalid signature
→ 401, unknown receipt → 404, no secret → 503).

## Governed actions from n8n (Phase 9.1)

The escalation flow above is Grace calling *out*. This is the reverse: any n8n
workflow — finance, ops, sales — asks Grace to govern an action **before** it
takes it, and switches on the verdict. Every call leaves a receipt, so a
workflow's actions are as auditable as an agent's.

### End-to-end

```
n8n workflow (invoice approval, refund, outbound email, …)
        │
   Execute Workflow ──> "Grace — Governed Action" sub-workflow
                                │
                     sign body (HMAC-SHA256, N8N_ACTION_SECRET)
                                │
        POST /webhooks/n8n/govern-action
        { workflow_id, workflow_run_id, project_id, agent_id,
          action_type, target, parameters, risk, mode }
                                │
        verify X-Axiom-Signature -> claim workflow_run_id (Redis, 24h)
                                │
             execute_governed_action  (the same service /v1/governance/govern uses)
                                │
        { verdict, receipt_id, reason, verify_url, corrected_parameters }
                                │
                    Switch on verdict:
                      allow   -> proceed
                      correct -> proceed with corrected_parameters (reserved)
                      deny    -> fail the workflow, with the reason + receipt
                      hold    -> wait; the escalation flow above resolves it
```

### Which endpoint do I use?

| Caller | Endpoint | Auth | Creates a receipt? |
|---|---|---|---|
| Your own code / SDK | `POST /v1/governance/govern` | Project API key | Yes |
| An n8n / Zapier / Temporal workflow | `POST /webhooks/n8n/govern-action` | HMAC over the raw body | Yes |
| Anything, "what would happen if…" | `POST /v1/preflight` | Project API key | No — advisory |
| An agent tool at runtime | `check_governance` in `workers/tools/base.py` | Worker gateway key | Yes |

All of them evaluate the same policy through the same service
(`services/governance/execute.py`), so a workflow cannot get a different answer
than an agent would for the same action.

### Design notes

- **Separate secret.** `N8N_ACTION_SECRET`, not `N8N_CALLBACK_SECRET`. The
  callback can only resolve a receipt Grace already created; this endpoint can
  originate one for any project. Unset returns `503` and never falls back.
- **Idempotency on the orchestrator's run id.** n8n retries; a retry must not
  produce a second receipt for one real-world action. `workflow_run_id` is
  claimed in Redis (`axiom:n8n:action:{workflow_id}:{workflow_run_id}`, 24h) and
  a replay returns the original receipt with `replayed: true`. A concurrent
  duplicate gets `409`.
- **`mode: "advise"`** maps to the engine's shadow mode: the action is evaluated
  and recorded truthfully, but the response reads `allow` so the workflow
  proceeds. Use it before letting a policy block production traffic.
- **Provenance.** `workflow_id` and `workflow_run_id` are written to the
  intent's metadata, so "which workflow did this?" is answerable from the audit
  chain rather than from n8n's logs.

### Non-goals

Grace does not schedule these calls, retain workflow state beyond the
idempotency key, retry on the workflow's behalf, or model steps, branches, and
resumption. n8n owns orchestration (AP-1.8, `docs/ANTIPATTERN_LIBRARY.md`).

### Config

```bash
N8N_ACTION_SECRET=dev_action_secret_change_me       # shared with n8n
N8N_ACTION_IDEMPOTENCY_TTL_SECONDS=86400            # optional
```

Import `n8n/governed-action-workflow.json` once and call it from any workflow —
see `n8n/README.md`.

**Tests:** `tests/test_n8n_action_webhook.py` (verdict + receipt, tampered body
-> 401, escalation secret rejected, missing secret -> 503, replayed run id ->
one receipt, concurrent duplicate -> 409, claim released on failure, advise mode,
workflow provenance on the intent).

## Semantic policy matching (pgvector)

When an agent action is evaluated, the exact/rule-based policy engine
(`services/policy/evaluator.py`, ordered rules, first-match-wins) stays the
source of truth for the verdict. **Semantic matching runs alongside it**: it
finds the policies most *similar in meaning* to an action and surfaces them as
advisory context, so an operator (or the agent) sees "these are the policies
this action is related to" even when no rule matched by exact fields.

**How it works**
- Each policy stores a 384-dim embedding of its text (name + description + rule
  descriptions) in `policies.embedding`, a pgvector `vector(384)` column with an
  HNSW cosine index. Embeddings are computed **on create/update**, best-effort:
  if embedding fails, the column stays `NULL` and the write (and governance)
  proceed normally.
- Search embeds the query and ranks policies by cosine similarity
  (pgvector `<=>`), scoped to the project.

**Embedding provider (swappable via env, `services/embeddings/`)**
- Default: **`fastembed`** with `BAAI/bge-small-en-v1.5` — local, free, offline,
  no API key. The model downloads once (~130 MB) and is cached.
- Optional: OpenAI `text-embedding-3-small` via `httpx`, with `dimensions=384`
  so the column never changes. Enable with:
  ```bash
  GRACE_EMBEDDING_PROVIDER=openai
  GRACE_EMBEDDING_MODEL=text-embedding-3-small
  GRACE_EMBEDDING_OPENAI_API_KEY=sk-...
  ```

**Requirements:** Postgres with the `vector` extension. `docker-compose.yml`
uses the `pgvector/pgvector:pg18` image; the migration runs
`CREATE EXTENSION IF NOT EXISTS vector`.

### Try it

```bash
# 1. Start Postgres (pgvector) + Redis, then migrate:
docker compose up -d postgres redis
uv run alembic upgrade head

# 2. Create a couple of policies (any project), e.g. one about deletions and one
#    about reading logs — embeddings are written automatically on create.

# 3. Semantic search — matches by meaning, not exact fields:
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/projects/<project_id>/policies/search?q=agent+wants+to+delete+the+users+table&k=5"
# -> {"data": [{"policy": {...}, "similarity": 0.97}, ...]}
```

**In the governance flow:** `POST /api/v1/preflight` accepts
`"include_related_policies": true`, which adds a `related_policies` array
(policy + similarity) to the response as advisory context — additive only, it
never changes the predicted verdict.

**Tests:** `tests/test_embeddings.py` (provider dispatch, dimension guard, the
OpenAI HTTP call mocked) and `tests/test_policy_semantic_search.py` (embed-on-
write + cosine ranking + project scoping through the endpoint, with the embedder
mocked to a deterministic keyword vector — no model download in CI).
