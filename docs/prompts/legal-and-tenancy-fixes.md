# Follow-up prompts: licensing, tenancy, and claim guardrails

Three prompts, run in order. **A** and **C** are low-risk. **B** is a security
fix and a deliberate breaking change to a wire contract.

Inherit the **House rules** block from
[`phase-9-build-prompts.md`](./phase-9-build-prompts.md) — paste it with each
prompt. Two additions to those rules:

- **ADR numbering:** Phase 9.1 consumed ADR-031. Before writing any ADR, run
  `grep -n "^## ADR-" docs/decisions.md | tail -3` and take the next free
  number. Do not assume.
- **Gate reporting:** `pytest`, `ruff`, and `mypy` are red at HEAD for
  pre-existing reasons. Never report a raw error count. Stash the change,
  re-run, and report the *set* difference — "identical set, zero new" or the
  specific new entries. `lint-imports` is genuinely green and can be read
  pass/fail on its own. Do not run `./axiom test`.

Context for all three: `docs/legal-posture.md` (new) is the source of truth for
what Grace may and may not claim. Read it first.

---

## Prompt A — Licensing and metadata truth

**Why:** the repository has no `LICENSE`, and package metadata contains a
factual misstatement of authorship. Both are cheap to fix and both are
embarrassing to leave.

### Tasks

**1. Add `LICENSE` — AGPL-3.0.**

Fetch the canonical text; **do not transcribe it from memory** — it is a legal
document and a paraphrase is worse than useless:

```
curl -fsSL https://www.gnu.org/licenses/agpl-3.0.txt -o LICENSE
```

Verify the file is ~34KB and begins with "GNU AFFERO GENERAL PUBLIC LICENSE
Version 3, 19 November 2007". Do not edit its body. Copyright attribution goes
in the metadata and README, not inside the licence text.

**2. Fix authorship in `packages/axiom-sdk/pyproject.toml`.**

It currently reads:

```toml
authors = [{ name = "AXIOM Control Systems Inc." }]
```

That entity does not exist. Replace with:

```toml
authors = [{ name = "Gagan Ganesh" }]
```

In the same file, update `description` — it still says "Python SDK for AXIOM"
and describes a "real-time hard governance and execution engine". Bring it in
line with the current product name and the claims register in
`docs/legal-posture.md` §1. Keep `license = "MIT"` — that split is deliberate
(see task 4).

**3. Add licence metadata where it's missing.**

- `apps/backend/pyproject.toml`: add `license = "AGPL-3.0-only"` and
  `authors = [{ name = "Gagan Ganesh" }]` to `[project]`.
- `apps/frontend/package.json`: it is `"private": true` with no licence field.
  Add `"license": "AGPL-3.0-only"` and `"author": "Gagan Ganesh"`.

**4. Document the licence split.**

`packages/axiom-sdk` stays MIT while the rest of the repo is AGPL-3.0. This is
intentional — an AGPL client SDK would impose copyleft on every application
that imports it. Add a short `packages/axiom-sdk/LICENSE` (MIT text, fetched
not transcribed) and a paragraph at the top of the SDK's README explaining the
split and pointing at `docs/legal-posture.md` §5.

**Do not** add SPDX headers to every source file. The licence is established by
`LICENSE` plus package metadata; per-file headers are churn with no legal
benefit here. If you disagree, raise it rather than doing it.

**5. ADR.** Record the licensing decision: AGPL-3.0 for the platform, MIT for
the client SDK, why the split exists, why the copyright holder is a natural
person rather than an entity, and that there is no CLA and no external
contributor yet (so the inbound position must be decided before the first
external patch — retroactive relicensing needs every contributor's consent).

### Done when

`LICENSE` exists and verifies; no file in the repo attributes authorship to
"AXIOM Control Systems Inc."; `grep -rn "AXIOM Control Systems" .` returns
nothing outside `.git`; the ADR is written.

---

## Prompt B — Close the cross-tenant credential hole

**Why:** `POST /webhooks/n8n/govern-action` takes `project_id` from the request
body and authenticates only with a single deployment-wide HMAC secret. Anyone
holding `GRACE_N8N_ACTION_SECRET` can mint governance receipts against **any
project in the deployment**. In an audit product, a credential that can forge
governance decisions across tenant boundaries is the worst-shaped defect
available. Fix this before Phase 9.0 or 9.2.

This is a deliberate breaking change to the endpoint's wire contract. The repo
is private with no external consumers, so there is no deprecation window — make
the clean change.

### Read first

- `docs/decisions.md` **ADR-026** — "MCP reuses project API keys instead of a
  passport credential". Same problem, same shape, already decided once. This
  change applies that precedent to the webhook surface.
- `axiom/services/api_key/service.py` — `APIKeyContext`, the `required_scope`
  check, constant-time comparison, revocation and expiry handling
- `axiom/routers/webhooks.py` — the current handler
- `axiom/services/governance/execute.py` — `execute_governed_action`
- `axiom/services/governance/idempotency.py` — `claim_run` / `release_claim` /
  `record_receipt`
- `tests/test_n8n_action_webhook.py` — the 14 tests you will be rewriting

### Design

**The API key becomes the sole authentication for this endpoint, and the sole
source of `project_id`. Remove the HMAC path.**

Rationale to record in the ADR: one credential means one rotation story and no
ambiguity about which mechanism is authoritative. More importantly, API keys are
**per-project and revocable** — a shared HMAC secret is neither, so there is no
way to revoke one workflow's access without breaking every workflow. The
escalation callback (`POST /webhooks/n8n/escalation-result`) **keeps** its HMAC:
it resolves a specific pre-existing receipt, so the receipt id itself bounds the
blast radius, and it is a genuinely different caller shape. Do not change it.

### Tasks

1. **Add a `workflow:govern` scope** to wherever the scope vocabulary is defined
   and validated (find it — `api_key` service and the key-creation router).
   Follow how `mcp:read` / `mcp:write` are declared.

2. **Rewrite the handler auth.** Replace the `X-Axiom-Signature` verification
   with API-key authentication resolving `required_scope="workflow:govern"`.
   Reuse the existing dependency if one exists; if the only caller today is a
   router-local helper, extract it so the webhook and the v1 routers share it.
   - Invalid/absent key → 401
   - Valid key without `workflow:govern` → 403
   - Revoked or expired key → 401

3. **Delete `project_id` from `N8nGovernActionRequest`.** Take it from
   `APIKeyContext.project_id`. The field must not be accepted at all — if a
   client sends it, Pydantic should reject the body rather than silently ignore
   it, so set the model to forbid extra fields if it does not already.

4. **Idempotency keys are now project-scoped.** The Redis key is
   `axiom:n8n:action:{workflow_id}:{workflow_run_id}` — with `project_id` no
   longer in the body, two projects using the same n8n instance can collide on
   `$execution.id`. Add the project id to the key. This is a correctness bug
   the tenancy fix would otherwise introduce.

5. **Remove `n8n_action_secret`** from `config.py` and `.env.example`, and the
   `N8N_ACTION_SECRET` env var from `docker-compose.yml`. Leave
   `N8N_CALLBACK_SECRET` alone — the escalation flow still uses it.

6. **Update `apps/backend/n8n/governed-action-workflow.json`.** The HMAC Code
   node goes away entirely; replace it with an HTTP Header Auth credential
   carrying the API key. The workflow gets simpler. Update
   `apps/backend/n8n/README.md` accordingly, including how to create a key with
   the `workflow:govern` scope.

7. **Update the "which endpoint do I use" table** in `apps/backend/README.md` to
   show the auth mechanism per endpoint.

### Tests

Rewrite `tests/test_n8n_action_webhook.py`. The signature tests are replaced by
auth tests. **The one that matters most:**

> a key issued for project A cannot produce a receipt against project B —
> assert on the persisted receipt's `project_id`, not just the response body.

That is the regression test for the hole being closed; write it first and watch
it fail against the current code before you change anything.

Also cover: missing key → 401; wrong scope → 403; revoked key → 401; body
containing `project_id` → 422; same `workflow_run_id` under two different
projects → two distinct receipts (the collision case from task 4); replay within
one project → identical `receipt_id`; in-flight duplicate → 409.

### ADR

Take the next free number. Context: the Phase 9.1 endpoint authenticated with a
deployment-wide HMAC secret and trusted a body-supplied `project_id`, making it
a cross-tenant governance credential. Decision: apply the ADR-026 precedent —
project API keys with a `workflow:govern` scope, project id from key context,
HMAC removed from this endpoint and retained on the escalation callback for the
stated reason. Consequences: per-workflow revocation becomes possible, the
idempotency key gains a project dimension, and the imported n8n workflow must be
re-imported by anyone using it.

---

## Prompt C — Guardrails so the claims can't drift

**Why:** `docs/legal-posture.md` §1 is only useful if the codebase cannot
quietly contradict it. Two cheap mechanisms.

### Tasks

**1. Claim guard in CI.** There is already a plain-text security scan in the
pipeline (it flagged a comment during Phase 9.1 — find it and follow its
pattern). Add a sibling check that fails when a forbidden claim string appears
outside `docs/legal-posture.md` and `docs/decisions.md`:

- `court-admissible`, `court admissible`, `courtroom-admissible`
- `tamper-proof`, `tamperproof`
- `FIPS validated`, `FIPS-validated`, `FIPS certified`
- `legally binding`
- `guarantees compliance`, `makes you compliant`, `ensures compliance`

Case-insensitive. The failure message should name the file and point at
`docs/legal-posture.md` §1. Allow an inline `# claim-ok:` escape comment for the
rare justified case, mirroring how the existing scan handles exceptions.

Expect this to flag `docs/phases/phase-8-0-grace-rebrand-and-ui.md:112`
("courtroom-admissible") — that is a historical phase document. Either add it to
the allowlist as history or reword it; do not silently delete phase history.

**2. Mandatory disclaimer on framework-named policy packs.** No compliance packs
ship today (`Policy.pack` defaults to `'custom'`), so this is a forward
constraint — implement it now, while it is free.

Add a validator in the policy service: if a pack name matches a known regulatory
framework (`ai-act`, `gdpr`, `hipaa`, `soc2`, `iso-27001`, `pci-dss` — make the
list a module constant so it is greppable), the policy's `description` must be
non-empty and must contain the template disclaimer. Provide the canonical string
as a constant:

> This pack is a configurable template. It has not been reviewed or endorsed by
> any regulator or standards body, and deploying it does not establish
> compliance with the framework it references. The deploying organisation
> remains responsible for its own compliance determination.

Reject the write with a clear validation error otherwise. Test both branches.

**3. Cross-link.** Add a line to `docs/decisions.md` above the ADR list, and to
`CONTRIBUTING` if one exists, pointing at `docs/legal-posture.md` as the
authority on product claims.

### Done when

The claim guard fails on a deliberately-introduced "court-admissible" string in
a source file and passes on the current tree; a policy write with
`pack="gdpr"` and no disclaimer is rejected; both paths are tested.
