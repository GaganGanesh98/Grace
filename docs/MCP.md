# Grace MCP Governance Server

Grace exposes its governance surface as [Model Context Protocol](https://modelcontextprotocol.io)
tools, so an agent can consult the policy engine and seal receipts through the
protocol it already speaks instead of requiring a bespoke HTTP integration.

The MCP layer is a transport, not a second governance implementation. A
`govern_action` call traverses the identical six-stage pipeline as
`POST /v1/govern` and produces a receipt in the same Merkle chain. There are no
second-class entries in the audit log.

---

## Tools

| Tool | Scope | Creates a receipt |
|---|---|---|
| `govern_action` | `mcp:write` | Yes |
| `check_policy` | `mcp:read` | **No** |
| `verify_receipt` | `mcp:read` | No |
| `get_receipt` | `mcp:read` | No |
| `list_policies` | `mcp:read` | No |

### `govern_action`

Submit an action for governance *before* performing it.

```
action    (object, required)  the action the agent intends to take
agent_id  (uuid,   required)  the registered agent taking it
mode      (string, optional)  "enforce" (default) | "shadow"
```

Returns the verdict, the reasoning and explanation, the receipt id, the Merkle
coordinates, and a public `verify_url`. The `decision` field states the outcome
in plain language and is the field an agent should read first.

Verdicts and their obligations:

- **approve** — proceed as submitted
- **deny** — do not perform the action, and do not retry a variation intended to
  evade the decision
- **modify** — discard the original action, use the returned `modification`
- **escalate** — stop; report that human approval is pending

`shadow` mode records a receipt without ever blocking. Use it to trial a policy
against live traffic before enforcing it.

Limits: 100 KB per action (canonical encoding), matching `POST /v1/govern`.

### `check_policy`

Dry-run evaluation. Returns the verdict `govern_action` *would* produce.

**This creates no receipt and is not an audit record.** It cannot be used as
evidence that an action was authorised. It exists so that consulting Grace is
cheap enough to do constantly; anything the agent intends to actually perform
must go through `govern_action`.

### `verify_receipt`

Runs four independent checks — Ed25519 signature, ML-DSA-65 (FIPS 204)
signature, RFC 6962 Merkle inclusion proof, and payload hash. All four must pass
for `verified` to be true. Same checks as `GET /v1/verify/{receipt_id}`.

### `get_receipt`

Receipt metadata within the caller's project. Never returns encrypted evidence
ciphertext or nonce.

### `list_policies`

The project's policies and their rules. Rules evaluate in order, first match
wins; no match means DENY. An agent that reads the rules can comply
deliberately rather than discovering boundaries through denials.

---

## Authentication

Grace does not issue a separate credential type for MCP. Use the existing
project API keys, minted with MCP scopes:

```bash
curl -X POST https://your-grace-host/api/v1/projects/$PROJECT_ID/api-keys \
  -H "Authorization: Bearer $YOUR_SESSION_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop", "scopes": ["mcp:read", "mcp:write"]}'
```

The full key is shown **once**. It looks like `axm_live_…` (or `axm_test_…`).

Scopes are explicit and non-overlapping with the HTTP API: a key holding only
`govern:write` cannot call `govern_action` over MCP. Granting an agent MCP
access is a deliberate act, not a side effect of having an API key. Mint a
read-only key (`["mcp:read"]`) for agents that should be able to consult
policy but never seal receipts.

Revocation takes effect immediately: write tools re-verify the key against the
database on every call, so revoking mid-session stops the next governed action
rather than the next session.

---

## Transports

### stdio (local agents)

The server runs as a subprocess of the agent runtime. The key is read once from
`AXIOM_API_KEY`.

```bash
export AXIOM_API_KEY=axm_live_...
export DATABASE_URL=postgresql+asyncpg://...
axiom-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "grace": {
      "command": "axiom-mcp",
      "env": {
        "AXIOM_API_KEY": "axm_live_your_key_here",
        "DATABASE_URL": "postgresql+asyncpg://axiom:axiom@localhost:5433/axiom",
        "REDIS_URL": "redis://localhost:6380/0"
      }
    }
  }
}
```

If you run the backend through `uv`, use `uv run axiom-mcp` as the command with
`"cwd"` set to `apps/backend`.

### Streamable HTTP (remote agents)

Mounted on the main API. The canonical endpoint is **`/mcp/` — with the
trailing slash**. Requests to `/mcp` are answered with a 307 redirect to
`/mcp/`; a 307 preserves method and body so redirect-following clients work
either way, but using the slashed form saves a round trip.

The key arrives per request:

```
Authorization: Bearer axm_live_...
```

`X-Api-Key` is also accepted, matching `POST /v1/govern`.

```json
{
  "mcpServers": {
    "grace": {
      "url": "https://your-grace-host/mcp/",
      "headers": { "Authorization": "Bearer axm_live_your_key_here" }
    }
  }
}
```

> **The trailing slash is required.** The endpoint is `/mcp/`, not `/mcp`. The
> bare path returns a 307 redirect that carries no body and no content-type,
> and the MCP SDK client does not follow it — the handshake fails with
> `Unexpected content type:`. If a client reports that error, check the slash
> before anything else.

Set `AXIOM_MCP_ENABLED=false` to disable the mount entirely.

---

## Trust boundaries

**stdio** has no network hop and no per-request identity. The key is bound for
the process lifetime. Anything able to read `AXIOM_API_KEY` from the process
environment could already impersonate it — treat the environment as the trust
boundary, not the transport.

**HTTP** resolves the key per request and binds the principal only for that
request's duration. Nothing is cached across requests beyond what `verify_key`
does internally.

Both transports enforce project tenancy on every tool call. A receipt belonging
to another project returns *not found*, never *forbidden*, so a caller cannot
use the MCP surface to confirm that an id exists in a tenant they cannot read.

---

## What this layer deliberately does not do

- **No caching of verdicts.** A cached verdict is an ungoverned action wearing a
  receipt's clothes. Every governed action goes through the pipeline.
- **No convenience tools that compose several calls.** Composition hides which
  action was actually governed.
- **No new crypto, policy, or Merkle code.** Those live in `axiom.services` and
  are shared with the HTTP surface. See `.importlinter` contract 5.
