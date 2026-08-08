# Phase 8.0 — Grace rebrand + UI/UX modernisation

**Status:** Ready to dispatch
**Branch:** `feat/grace-rebrand-ui`
**Commits:** one per part (four total)

---

## Context

The product is Grace. The codebase still says AXIOM in ~1100 places, but those
places are not equivalent — some are copy on a page, some are a wire protocol,
and one is data already sitting in the database. This phase renames what is safe
to rename, defers what needs a migration, and separately reworks the visual
design.

Do **not** run a repo-wide `sed s/axiom/grace/g`. It will break
`uvicorn axiom.main:app`, the Alembic env, the installed console scripts, and
every API key in the database. The tiers below exist for that reason.

---

## Part 1 — User-facing rename (safe, do first)

Everything a user reads. 44 occurrences in the frontend plus a handful of
backend strings. No identifier changes, no wire changes.

Frontend:

- `app/layout.tsx` — `title: "AXIOM"` → `"Grace"`
- `app/login/page.tsx` — wordmark `AXIOM`, and the corner meta
  `AXIOM :: VERIFICATION LAYER`
- `app/verify/[id]/page.tsx` — the `AXIOM` wordmark and
  "Verified by AXIOM — post-quantum cryptographic governance"
- `components/command-center/sidebar.tsx` — the `AXIOM` / `COMMAND CENTER`
  lockup
- `components/command-center/empty-state.tsx` — two body strings
  ("AXIOM signs and governs every action…", "…run it through AXIOM so every
  action is governed and signed")
- Comments in `app/globals.css` and `app/login/login.module.css`

Backend user-visible strings:

- `main.py` — `FastAPI(title="AXIOM API", ...)`
- Any docstring or response copy that names the product to a caller

Also update `README.md` and `docs/*.md` prose. Leave code identifiers in docs
alone — if the doc says `axiom.main:app`, that is still correct after this part.

**Check:** `grep -rn "AXIOM\|Axiom" apps/frontend/app apps/frontend/components`
returns only identifier names (Part 2), not display copy.

---

## Part 2 — Frontend identifier rename (safe, no runtime contract)

TypeScript-internal names. Nothing outside the frontend bundle observes these.

- `lib/events/axiom-events-context.tsx` → `grace-events-context.tsx`
- `lib/events/use-axiom-events.ts` → `use-grace-events.ts`
- `AxiomEventsProvider` → `GraceEventsProvider`
- `useAxiomEventsContext` → `useGraceEventsContext`
- `useAxiomEvents` → `useGraceEvents`
- `AxiomEvent`, `AxiomEventsStatus`, `AxiomEventsValue` → `Grace*`
- CSS custom property `--axiom-font-scale` → `--grace-font-scale`
  (grep for it — it is read in `font-scale-provider.tsx` as well as CSS)

**Check:** `npm run build` and `npx tsc --noEmit` clean; `npm test` (vitest)
still 77/77.

---

## Part 3 — Deferred: identifiers with a contract (DO NOT DO IN THIS PHASE)

Record these in `docs/decisions.md` as a deliberate deferral with the reasoning
below. Each needs its own migration, not a rename commit.

| Thing | Count / risk | Why it can't be a find-replace |
|---|---|---|
| `axiom` Python package | 1067 import sites | Renaming changes `uvicorn axiom.main:app`, `alembic/env.py`, `[project.scripts]` entry points, the `packages/axiom-sdk` distribution name, and the namespace-collision guard at the top of `tests/conftest.py`. Mechanically doable, but it is its own phase with its own full-suite verification. |
| `axm_live_` / `axm_test_` | 28 code sites + **live DB rows** | This is **data**, not code. `api_keys.key_prefix` stores the first 16 chars and `verify_key` narrows on it. Changing the constant orphans every existing key. Needs either a dual-prefix accept window or a deliberate re-mint. |
| `AXIOM_*` env vars (~40) | `.env`, Railway, docker-compose, CI | Every deployment target has these set. Rename requires `AliasChoices("GRACE_X", "AXIOM_X")` on every setting for a compat window, then a later removal. |
| `X-Axiom-Receipt-Id`, `X-Axiom-Vault-Key`, `X-Axiom-Agent-Id`, `X-Axiom-Signature` | wire protocol | Emitted by the gateway, read by clients and the agent worker. Needs dual-emit / dual-read before the old form can be dropped. |
| `axiom-postgres`, `axiom-redis`, `axiom_pg_data`, DB name/user `axiom` | local + deployed state | Renaming the volume orphans the data. Renaming the DB user requires a migration. |
| `./axiom` CLI | muscle memory + docs | Cheap, but rename it in the same phase as the package so there's one cutover, not two. |

If you want Tier 3 sooner: the honest sequencing is **package rename first**
(biggest, purely mechanical, fully covered by the test suite), then env vars
with aliases, then headers with dual-emit, and the key prefix **last** because
it is the only one that touches stored data.

---

## Part 4 — Visual design

### Read the current system before changing it

`app/globals.css` is not an accident. It is a coherent IBM Carbon-derived
system: IBM Plex Sans/Mono, Carbon's exact status ramp (`#fa4d56` denied,
`#f1c21b` held, `#42be65` ok), 2–8px radii, 36px table rows, a documented
motion scale (80/120/180/240ms), and a deliberate rule that brand cyan
(`--cyan-400`) is **reserved for the live indicator only**.

Whatever replaces it must be equally systematic. Do not scatter one-off hex
values and ad-hoc `transition: all 0.3s` through components.

### The constraint that matters

Grace's product is *evidence*. The UI's job is to make a signed receipt feel
trustworthy and a denial feel serious. "Modern and fashionable" in the
consumer-SaaS sense — heavy gradients, glassmorphism, bouncy spring animations,
playful illustration — actively works against that. A courtroom-admissible
audit trail rendered in the visual language of a habit-tracker reads as
unserious, and that is a product problem, not a taste problem.

Aim for **contemporary and confident, not decorative**. Reference points worth
studying: Linear (density + restraint + excellent motion), Vercel dashboard
(typographic hierarchy on near-black), Stripe (how it renders money-critical
state without drama). All three are unmistakably modern and none of them are
playful.

### What to actually change

Keep: the token architecture, the semantic status ramp (those colours carry
meaning and are accessibility-tuned), the density anchors, IBM Plex Mono for
hashes/IDs/receipts — monospace is doing real work there.

Change:

1. **Surface palette.** The current `#0a1628` family is a blue-heavy navy that
   reads slightly dated and muddies the status colours sitting on it. Move to a
   more neutral near-black with a subtle cool cast (roughly `#0B0C0E` page /
   `#111214` card / `#17181B` elevated), which makes the semantic colours pop
   without raising their saturation. Keep contrast at WCAG AA minimum for body
   text — verify, don't eyeball.

2. **Typography.** IBM Plex Sans is legible but institutional. Consider Inter
   or Geist for UI text while keeping IBM Plex Mono (or swapping to JetBrains
   Mono / Geist Mono) for cryptographic material. Tighten the type scale and
   increase heading weight contrast — the screenshots show headings and body
   too close in visual weight.

3. **Depth.** Replace flat 1px borders everywhere with a layered approach:
   subtle border **plus** a very low-opacity inner highlight on raised surfaces.
   One elevation step, not five.

4. **Empty states.** Four of the nine screens shown are empty states, and they
   are the first thing a new user sees. They deserve real design attention:
   an icon or diagram with actual character, a clear primary action, and one
   line explaining *why* the screen is empty rather than just that it is.

5. **The sidebar.** Currently a flat list. Add an active-item treatment with a
   moving indicator, group the nav (workspace / evidence / config), and give
   the project switcher more presence — "NO PROJECT" in a grey box is the
   weakest element on screen and it gates everything else.

### Motion

Extend the existing motion tokens rather than inventing a parallel system.

- Respect `prefers-reduced-motion` — non-negotiable, wrap every animation.
- **Page/route transitions:** 180–240ms fade + 4–8px rise. No slide-across.
- **List/table rows:** stagger children by ~20ms on mount, cap the stagger at
  ~8 items so long lists don't crawl.
- **Sidebar active indicator:** shared-layout animation (Framer Motion
  `layoutId`) so it slides between items.
- **Status/verdict badges:** a brief scale-in on first render. Deny/held should
  *not* pulse continuously — a permanently animating error is fatigue, not
  signal.
- **Receipt verification:** this is the moment worth spending motion budget on.
  The four checks (Ed25519, ML-DSA-65, Merkle inclusion, payload hash) resolving
  in sequence with a checkmark each is the single most persuasive animation in
  the product. Build that one properly.
- **Skeletons** rather than spinners for data loads.
- Numbers that change (counts, tree size) — animate the transition, don't snap.

Suggested library: **Framer Motion** (`motion/react`). It's the standard for
React 18 + Next 14, has `layoutId` for the sidebar, and honours reduced-motion.
Add it to `apps/frontend/package.json`; do not hand-roll keyframes for layout
animation.

Keep durations at or under the existing `--motion-slow: 240ms`. A governance
tool should feel immediate. Anything above ~300ms reads as sluggish under
repeated daily use.

---

## Definition of done

- No user-visible "AXIOM" string remains anywhere in the running app —
  check every route in the screenshots: `/dashboard`, `/projects`, `/agents`,
  `/vault`, `/receipts`, `/ledger`, `/policies`, `/settings`, `/login`,
  `/verify/[id]`.
- `npx tsc --noEmit` clean, `npm run build` succeeds, vitest still passing.
- Backend untouched by Parts 1–2 except display strings — `pytest` unaffected.
- Every animation wrapped in a `prefers-reduced-motion` guard.
- Contrast ratios verified against WCAG AA, not judged by eye.
- Tier 3 deferral recorded as an ADR with the sequencing above.
- Before/after screenshots of all nine routes in `docs/verification/`.

---

## Note on scope

Parts 1–2 are a few hours. Part 4 is not — a coherent redesign across nine
routes plus a motion system is days of work, and it is the kind of thing that
degrades badly if rushed halfway. If time is short, do Parts 1–2 and the
palette/typography change from Part 4, ship that, and treat the motion system
and empty-state redesign as Phase 8.1. A half-restyled app looks worse than
either the old one or the new one.
