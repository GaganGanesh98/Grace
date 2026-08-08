# n8n workflows

Two importable workflows. They face in opposite directions and use **different
secrets** — see the trust-boundary note below.

| File | Direction | Secret | Purpose |
|---|---|---|---|
| `escalation-workflow.json` | Grace → n8n → Grace | `N8N_CALLBACK_SECRET` | Grace held an action; n8n decides and calls back |
| `governed-action-workflow.json` | n8n → Grace | `N8N_ACTION_SECRET` | A workflow asks Grace to govern an action it is about to take |

## Governed Action (reusable sub-workflow)

The point of this one is that you import it **once** and every other workflow —
finance, ops, sales — calls it with an Execute Workflow node. Nobody has to
understand HMAC signing or the governance API to add "ask Grace" to a workflow.

```
Execute Workflow Trigger
        │
   Sign Request  (Code: build body once, HMAC-SHA256 it)
        │
   Ask Grace     (HTTP POST /webhooks/n8n/govern-action, raw body)
        │
   Switch On Verdict
        ├── allow   → return the original parameters
        ├── correct → return corrected_parameters (reserved; not emitted today)
        ├── deny    → throw, with the reason and the receipt id
        └── hold    → Wait, then re-check (a human or the escalation flow decides)
```

### Import it

1. n8n → **Workflows → Import from File** → `governed-action-workflow.json`.
2. Set `N8N_ACTION_SECRET` in the n8n environment to match the backend's. It is
   already wired in `docker-compose.yml` for local dev.
3. Optionally set `GRACE_API_URL` in n8n (defaults to
   `http://host.docker.internal:8000`, which is what the compose stack needs).
4. Save. Leave it inactive — a sub-workflow is invoked, not triggered.

### Call it from another workflow

Add an **Execute Workflow** node pointing at "Grace — Governed Action" and pass:

```json
{
  "project_id": "<uuid>",
  "agent_id": "n8n-finance",
  "action_type": "payment.send",
  "target": "https://api.stripe.com/v1/transfers",
  "parameters": { "amount": 4200, "currency": "usd" },
  "risk": "high",
  "mode": "enforce"
}
```

`mode: "advise"` evaluates the action and writes a receipt but always answers
`allow` — use it to see what a policy *would* do before you let it block a live
workflow.

### Why two secrets

The escalation callback can only resolve a receipt Grace already created. The
governed-action endpoint can *originate* one, for any project. Different blast
radius, so different key: leaking the callback secret does not let someone
manufacture governance decisions. The backend returns `503` when
`N8N_ACTION_SECRET` is unset and never falls back to the callback secret.

### Idempotency

`workflow_run_id` (n8n's `$execution.id`) is the idempotency key. n8n retries —
on timeout, on 5xx, on a human clicking "retry execution" — and each retry
reuses that id, so Grace returns the original receipt rather than governing the
same real-world action twice. The claim lives in Redis for 24h
(`N8N_ACTION_IDEMPOTENCY_TTL_SECONDS`).

If two calls race, the second gets `409` — retry it. That is deliberate: a
duplicate receipt is worse than a retry.

### What Grace does not do

Grace does not schedule these calls, retain workflow state beyond the
idempotency key, retry on the workflow's behalf, or model steps and branches.
n8n owns orchestration; Grace answers one question about one action and leaves
a receipt. See AP-1.8 in `docs/ANTIPATTERN_LIBRARY.md`.
