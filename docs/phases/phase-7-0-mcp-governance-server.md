# Phase 7.0 — MCP Governance Server

**Status:** Ready to dispatch
**Prerequisite:** Phase 6.7 (Provider Fabric) should land first — see `PHASE_6_7_BACKLOG.md`. The `generic_proxy` credential gap is in the path this phase exposes to third parties.
**Branch:** `feat/mcp-governance-server`

---

## Why this phase

Grace governs AI agents. Agents speak MCP. Today the only way to reach Grace's
governance is an HTTP call to `POST /v1/govern` that a developer has to wire by
hand — which means Grace governs agents only when someone remembers to integrate it.

An MCP server inverts that: Grace becomes a tool the agent already has. The agent
asks "may I do this?" before acting, and the answer is a signed, Merkle-anchored
receipt. That is Grace's entire value proposition delivered through the protocol
its market already uses.

This is deliberately **not** a new governance implementation. Every primitive
already exists and is stronger than what comparable MCP layers sit on:
`services/policy/evaluator.py` (ALLOW/DENY/MODIFY/ESCALATE), `services/crypto/`
(Ed25519 + ML-DSA-65 hybrid), `services/receipt/` (RFC 6962 Merkle),
`services/pipeline/` (six-stage runner). Phase 7.0 is a **transport and tool
surface** over them. If you find yourself writing crypto or policy logic, stop —
you are in the wrong layer.

---

## Scope

### In scope

- An MCP server exposing Grace governance as tools, served over **stdio** (local
  agent processes) and **streamable HTTP** (remote agents).
- Authentication reusing the existing API key system — no new credential type.
- Every state-changing tool call produces a receipt through the existing pipeline.
- Scope enforcement so a key can be issued read-only.

### Out of scope — do not build

- Knowledge graph, entity/edge ingestion, clustering, graph-ranked search.
- Source connectors (GitHub/Linear/Slack/Notion/Gmail).
- Any 3D or graph visualisation.
- A new passport/credential system. **Use `axm_live_` / `axm_test_` API keys.**
- Changes to the six-stage pipeline, policy evaluator, signing, or Merkle code.

If the work seems to require touching `services/crypto/`, `services/policy/`, or
`services/pipeline/stages/`, raise it rather than editing — that is a signal the
tool surface is wrong.

---

## Part 1 — Transport and auth

Create `apps/backend/src/axiom/mcp/`:

```
mcp/
  __init__.py
  server.py      # MCP server construction, tool registration
  transport.py   # stdio entrypoint + ASGI app for HTTP mount
  auth.py        # API-key -> APIKeyContext resolution for MCP sessions
  tools.py       # tool definitions (Part 2)
  schemas.py     # Pydantic in/out models per tool
```

**Auth.** Reuse `axiom.services.api_key.service.verify_key`, which returns
`APIKeyContext(api_key_id, project_id, created_by_user_id, scopes, key_prefix)`
and already does prefix-narrowing plus `hmac.compare_digest`. Do not reimplement
key checking.

- **HTTP transport:** `Authorization: Bearer axm_live_...`.
- **stdio transport:** read the key from `AXIOM_API_KEY` env var. stdio is a
  local trust boundary; document that clearly in the module docstring.
- Resolve the key **once per session**, not per tool call, but re-check
  `revoked_at` on each *write* tool call so revocation takes effect immediately.
- On failure return an MCP protocol error, never a partial result. No tool may
  execute without a resolved `APIKeyContext`.

**Scopes.** `verify_key` already accepts `required_scope`. Define two:

- `mcp:read` — `check_policy`, `verify_receipt`, `get_receipt`, `list_policies`
- `mcp:write` — `govern_action`

A key with only `mcp:read` calling `govern_action` gets a clear scope error.
Every tool declares its required scope in one place — do not scatter scope
strings through handler bodies.

**Project scoping.** `APIKeyContext.project_id` is the tenancy boundary. Every
query must filter on it. There is no cross-project MCP access; a tool that
cannot resolve a resource inside the caller's project returns **not found**, not
forbidden — this matches Grace's existing enumeration-resistance behaviour
(see the 404-not-403 pattern in the project routers).

---

## Part 2 — The tools

Five tools. Resist adding more; each one is API surface you maintain forever.

### `govern_action` (write, `mcp:write`)

The headline tool. Input mirrors `GovernanceRequest` in
`schemas/governance.py`: `action: dict`, `agent_id: UUID`, `mode:
PipelineMode` (default `ENFORCE`).

Call `ReceiptService(db).process(project_id=..., agent_id=..., api_key_id=...,
correlation_id=..., action=..., mode=...)` — the same path `routers/govern.py`
uses. Return the verdict, reasoning, explanation, any modification, receipt id,
Merkle coordinates, and `verify_url`.

The response text an agent sees must make the verdict **unambiguous in prose**,
not just in a structured field. An LLM reading `{"verdict": "deny"}` in a blob
of JSON may proceed anyway. Lead with the decision in plain language, then the
receipt data. On `MODIFY`, state clearly that the agent must use the modified
action rather than its original.

Honour the existing 100 KB action cap and the `100/minute` rate limit
(`api_key_limit_key`).

### `check_policy` (read, `mcp:read`)

Dry-run evaluation: what *would* the verdict be, without dispatching or sealing
a receipt. Runs the policy evaluator only.

This is the tool that makes Grace cheap for an agent to consult constantly.
Document in the tool description that it produces **no receipt** and is therefore
not an audit record — an agent that wants provenance must call `govern_action`.

### `verify_receipt` (read, `mcp:read`)

Wrap the logic behind `GET /v1/verify/{receipt_id}`. Return the four checks
already modelled in `VerificationDetails` — `ed25519_signature_valid`,
`ml_dsa_signature_valid`, `merkle_inclusion_valid`, `payload_hash_matches` —
plus the inclusion proof.

Verification is public by design in Grace. Keep it working with a valid key here,
but do not weaken the public endpoint.

### `get_receipt` (read, `mcp:read`)

Fetch a single receipt by id within the caller's project. Lets an agent inspect
its own audit trail.

### `list_policies` (read, `mcp:read`)

Return active policies for the project — id, version, human-readable summary.
An agent that can read the rules can comply with them instead of guessing.
Return the rule structure, never any secret material.

---

## Part 3 — Wiring, docs, tests

**Mount.** Add the HTTP transport to `main.py` alongside the existing
`app.include_router(...)` block, prefix `/mcp`. Add a stdio console entry point
in `apps/backend/pyproject.toml` (e.g. `axiom-mcp = "axiom.mcp.transport:main"`)
so `uvx`/`npx`-style local launch works.

**Import contracts.** `.importlinter` enforces layering. `axiom.mcp` sits at the
**router layer** — it may import `axiom.services`, must not be imported *by*
`axiom.services`, `axiom.models`, or `axiom.core`. Add a contract making that
explicit rather than relying on the existing layers contract to catch it.

**Docs.** `docs/MCP.md`: the five tools with signatures, both transports, how to
mint a scoped key, and a copy-pasteable Claude Desktop / MCP client config block.
Add an ADR to `docs/decisions.md` recording the decision to reuse API keys rather
than introduce a passport type, and why (one credential system, existing
revocation, existing scope model, no new secret storage).

**Tests.** CI gate is ≥80% line coverage; pre-commit blocks broad `except` and
`print()` in backend source. Cover:

- Auth: valid key resolves; revoked key rejected; wrong/missing key rejected;
  `mcp:read`-only key rejected on `govern_action`.
- Tenancy: a key for project A cannot read a receipt from project B (asserts
  **not found**, not forbidden).
- `govern_action` produces a receipt that `verify_receipt` then validates —
  end-to-end through the real pipeline, not mocks.
- `check_policy` creates **no** receipt row (assert the count is unchanged).
- Both transports resolve auth identically.
- Rate limit and the 100 KB body cap apply.

---

## Definition of done

- Both transports serve all five tools against a real key.
- A real MCP client (Claude Desktop config from `docs/MCP.md`) connects, lists
  tools, and completes a `govern_action` → `verify_receipt` round trip.
- No changes to `services/crypto/`, `services/policy/evaluator.py`, or
  `services/pipeline/stages/`.
- `ruff`, `mypy`, `import-linter`, and the full backend suite pass; coverage ≥80%.
- Three commits, one per part.

---

## Notes for the implementer

The temptation in this phase is to make the MCP layer "smart" — caching
verdicts, batching, adding convenience tools that compose several calls. Don't.
The value is that every governed action goes through the identical audited path
as `POST /v1/govern`, so the receipt chain has no second-class entries. A cached
verdict is an ungoverned action wearing a receipt's clothes.

The other temptation is a new credential type, because "passport" sounds more
correct for an agent than "API key". It isn't worth a second credential system
with its own revocation, scoping, and storage. Grace's API keys already carry
project scoping, expiry, revocation, and scope lists. Use them.
