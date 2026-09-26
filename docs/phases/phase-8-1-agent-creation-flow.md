# Phase 8.1 — Fix agent creation dead-end

**Status:** Ready to dispatch
**Branch:** `fix/agent-creation-flow`
**Commits:** one per part (three total)

---

## What happened

A new user created a project, clicked **+ NEW AGENT**, filled in a name and a
system prompt, and could not submit. The form requires a vault key, the vault
was empty, and the only signal was a line of amber text above a permanently
disabled button. Nothing earlier in the flow said a credential was needed.

Two separate defects:

1. **A silent failure** — `apps/frontend/components/agent-definitions/agent-form.tsx:63–68`.
   The submit handler checks whether the selected key's service is supported and,
   if not, does a bare `return` with no error state set. The user clicks
   "Create agent" and *nothing happens* — no message, no spinner, no network
   call. This will bite as soon as a credential exists but is the wrong type
   (a Tavily tool key, or any provider outside the hardcoded allowlist).

2. **An undeclared dependency** — the Command Center quickstart
   (`components/command-center/empty-state.tsx`) presents the flow as
   `01 PROJECT → 02 AGENT → 03 RUN`. The real dependency chain is
   `PROJECT → CREDENTIAL → AGENT → RUN`. The user is invited to do step 2
   before its prerequisite exists, and only discovers this after typing a name
   and a prompt — which are then lost on navigating away to the vault.

Related smaller problems in the same file:

- `agent-form.tsx:116–126` — when `vaultKeys` is empty the `<select>` renders
  with zero `<option>` children, so it can never hold a valid UUID. There is no
  placeholder option and no disabled state on the control itself.
- `agent-form.tsx:100–108` — Model is a free-text `Input` defaulting to
  `"groq/llama-3.3-70b-versatile"`, with no relationship to the selected vault
  key's provider. Choosing an OpenAI credential and leaving the Groq model
  string produces an agent that fails at *run* time, not at creation time.
- `agent-form.tsx:154–160` — the disabled submit button carries no `title` or
  `aria-describedby` explaining *why* it is disabled.

---

## Part 1 — Never fail silently

The bare `return` must go. Replace the pre-submit provider check with real,
surfaced validation.

- Move the supported-provider list out of the component into a shared constant
  (e.g. `lib/llm-providers.ts`) exporting `SUPPORTED_LLM_SERVICES` and a
  `isSupportedLlmService(service: string): boolean`. It is currently an inline
  array literal inside a submit handler, which is why it is easy to miss.
- Make the check a **zod refinement** or an explicit `setError("vault_key_id", …)`
  so the message renders through the existing `errors.vault_key_id` path, next
  to the field it concerns.
- Message should name the problem and the fix: *"`{name}` is a {service}
  credential. Agents need an LLM provider key — OpenAI, Anthropic, Google,
  Groq, or xAI."*
- Filter the vault-key `<select>` to supported services in the first place, so
  the invalid state is hard to reach. Keep the validation anyway — filtering the
  options is a convenience, not a guarantee.

**Invariant to hold:** every click of an enabled "Create agent" button results
in either a network request or a visible error. Never a no-op.

---

## Part 2 — Make the dependency visible before the user invests effort

### Quickstart

`components/command-center/empty-state.tsx` — change the three cards to four,
matching the real chain:

```
01 PROJECT     Create a workspace.
02 CREDENTIAL  Add an LLM provider key to the vault. Agents need one to run.
03 AGENT       Register an agent definition.
04 RUN         Submit a run; every governed action returns a verifiable receipt.
```

Mark each card done/pending against actual state (project exists? vault
non-empty? agent exists?) rather than rendering four static cards. A user
should be able to see at a glance which step they are on.

### Gate the entry points, don't gate the submit button

The sidebar **+ NEW AGENT** quick action and the project-overview
**+ NEW AGENT** button currently open a form the user cannot complete. When the
vault has no supported LLM credential, they should instead open the credential
flow first — either route to `/dashboard/vault` with a return path, or open the
Add Credential dialog inline. Blocking at the *entry* is far better UX than
letting someone type a system prompt into a form that was never submittable.

If you keep the form reachable in that state, then at minimum:

- Give the disabled button a `title` explaining the blocker.
- Render the empty-vault message as a proper callout with the CTA as a button,
  not a text link buried above the fields.

### Do not lose the user's work

The current "Add one in Vault →" link is a hard navigation. Name, model, and
system prompt are discarded. Fix by either:

- keeping the user in place (modal-over-modal or an inline credential step), or
- persisting the draft (`sessionStorage`, keyed per project) and restoring it
  when they return, with the return trip wired via a `?returnTo=` param so
  "Add credential" lands them back on the agent form.

The first option is better. Choose the second only if the credential dialog
cannot be nested.

---

## Part 3 — Couple model to provider

Free-text model with an unrelated provider key is a runtime failure waiting to
happen, and the failure surfaces during a *governed run* — the worst place for
a typo to land.

- Derive the model options from the selected vault key's `service`. There is
  already a provider registry on the backend
  (`apps/backend/src/axiom/gateway/provider_registry.py`, 13 providers with
  `base_url` and protocol shape) — expose the model list from there rather than
  hardcoding a second list in the frontend, or the two will drift.
- Make Model a `<select>` populated from the chosen provider, with a
  free-text escape hatch for models the registry does not know yet.
- When the vault key changes, reset the model to that provider's default rather
  than leaving a stale string from the previous provider.

If exposing models from the backend is more than this phase should carry, then
at minimum validate that the model string's provider prefix matches the
selected key's service, and surface a field error when it does not.

---

## Tests

Frontend (vitest + testing-library), in `apps/frontend/__tests__/`:

- Empty vault: submit button disabled **and** an accessible explanation present.
- Unsupported-service key selected: clicking Create renders a visible error and
  fires **no** network call. (This is the regression test for the silent
  return — assert on both halves.)
- Supported key: submit calls `onSubmit` once with the expected payload.
- Vault-key select renders a placeholder option when the list is empty.
- Draft preservation: fill name + prompt, trigger the credential detour, return,
  fields still populated.
- Quickstart renders four steps and marks completed ones from state.

---

## Definition of done

- With an empty vault, a new user is routed to add a credential *before*
  reaching the agent form — no dead-end.
- No code path exists where an enabled submit button does nothing.
- Typed input survives the credential detour.
- Model options follow the selected provider.
- `npx tsc --noEmit` clean, `npm run build` succeeds, vitest green including the
  new cases.
- Manual walkthrough from a fresh project → credential → agent → run, with
  screenshots in `docs/verification/`.

---

## Note

Part 1 is the actual bug and is maybe an hour. Parts 2 and 3 are the reason the
bug was reachable at all. If you only do one, do Part 1 — a button that silently
does nothing is the kind of thing that makes a user assume the whole product is
broken.
