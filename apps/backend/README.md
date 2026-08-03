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
  AXIOM_EMBEDDING_PROVIDER=openai
  AXIOM_EMBEDDING_MODEL=text-embedding-3-small
  AXIOM_EMBEDDING_OPENAI_API_KEY=sk-...
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
