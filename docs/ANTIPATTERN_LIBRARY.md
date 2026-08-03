# AXIOM V1 → V2 ANTI-PATTERN LIBRARY

**Purpose:** Every mistake from V1, named so it's rejectable in future decisions.
**Use:** Reference at every phase. Every Cursor prompt cites the relevant anti-patterns it prevents.
**Source:** Extracted from dual-agent audit, 45-bug fix post-mortem, 3,983-line transcript, every AXIOM chat.
**Status:** Canonical. Append new entries as v2 reveals new traps. Never delete.

---

## 📊 V1 BY THE NUMBERS (what you're routing around)

| Metric | V1 Value | V2 Target | Reduction |
|---|---|---|---|
| Lines of code | 231,000 | 15,000-20,000 | ~12× |
| Database tables | 130+ | ~10 (Phase 1), ~15 (Phase 2) | ~10× |
| Migrations | 141 (→ reset to 107) | ~25 total | ~5× |
| API endpoints | 500+ | ~30-35 at launch | ~15× |
| "Phases" built | 40+ | 8 named phases | ~5× |
| Biological intelligence systems | 41 | 0 (deferred post-revenue) | — |
| `except: pass` blocks | 110+ | 0 (ruff-enforced) | — |
| Seed rows | 42,000+ | <100 | ~420× |
| Customers using it | 0 | ≥1 before Phase 5 | — |
| Dual-agent audit scores | Crypto 9/10, Pipeline 8/10, **Product 1/10, Security 6/10, Error Handling 5/10** | Target all ≥8/10 | — |

**The single number that matters:** **1/10 product layer.** Everything else was in service of a product nobody could use.

---

## 🎯 THE META-PATTERN (the one pattern that caused all others)

**Anti-Pattern #0 — "BOTTOM-UP BUILD TRAP"**
- *What it is:* Build infrastructure → build engine → build intelligence → build optimization → eventually build product surface. The "eventually" never comes.
- *How it shows up:* Every new phase adds depth without asking "can a human use this today?"
- *Why it's seductive:* Infrastructure feels like foundation. It's actually just deeper dirt.
- *V2 prevention:* **Every phase MUST end with something a human can use via browser.** Phase 1 ends with login working. Phase 2 ends with `/v1/govern` returning a signed receipt. Phase 3 ends with 10 UI pages. No phase is "done" until a human can touch the output.
- *Detection signal:* If you can't write a one-sentence "user can now do X" for the phase deliverable, the phase is wrong.

**This is the anti-pattern that spawned all others. Every other pattern below is a specific instance.**

---

## 🏗️ CATEGORY 1 — ARCHITECTURAL SINS (building too much)

### AP-1.1 — "NUCLEAR REACTOR INSTEAD OF GENERATOR"
- *V1:* Built 41 biological intelligence systems (metabolism, dormancy, spike bus, DNA genome encoder, 8 agent senses, consciousness mesh, temporal prophecy, governance dreaming, 6-cortex decision evaluation, agent speciation/fusion/light split) before shipping the basic `/v1/govern` endpoint.
- *V2 prevention:* First Principles test — "is this required for the value proposition in one sentence?" (Agent does thing → policy evaluates → receipt signed → anyone verifies). If no, defer.
- *Rule:* No R&D systems before revenue. Intelligence layers come AFTER 10 paying customers.

### AP-1.2 — "8 GOVERNANCE MODES (OAM TRAP)"
- *V1:* 8 OAM (Observability-Actuation Matrix) governance modes. Real need: 2-3 (Enforce, Shadow, maybe Audit).
- *V2 prevention:* Start with 2 modes (Shadow, Enforce). Add Audit only when a customer asks for "log-only without enforcement." Never add a 4th unless paid-customer demand.
- *Rule:* Enumerations that exceed 5 entries at launch are suspicious. Enumerations that exceed 10 are always wrong.

### AP-1.3 — "6-CORTEX DECISION EVALUATION"
- *V1:* Six parallel decision evaluators for a system where nobody was making decisions yet.
- *V2 prevention:* One policy engine. Multiple evaluators come when customers report conflicting policy decisions requiring meta-resolution. Not before.

### AP-1.4 — "AGENT SPECIATION / FUSION / LIGHT SPLIT"
- *V1:* Beautiful biological metaphors for a system with zero agents to speciate.
- *V2 prevention:* Ban biological metaphors from code and docs. Name things after what they do (`PolicyEvaluator`, not `Cortex`). See also AP-5.x (naming sins).

### AP-1.5 — "ORG → GOVERNANCE BOUNDARY → PROJECT HIERARCHY"
- *V1:* Three-tier hierarchy with zero multi-org customers.
- *V2 prevention:* User → Project. Flat. Add Org when the first multi-org customer signs a contract.
- *Rule:* Hierarchy depth must match customer cardinality. If you have N=0 enterprise customers, you have N=0 enterprise hierarchy levels.

### AP-1.6 — "4-ROLE RBAC (OWNER/ADMIN/OPERATOR/VIEWER)"
- *V1:* 4 roles × N permissions = combinatorial RBAC matrix nobody needed.
- *V2 prevention:* OWNER + MEMBER. Two roles. Phase 1 ships with that. ADMIN only appears when a project reports a real "I need someone who can manage members but not billing" scenario.

### AP-1.7 — "AUP (AXIOM UNIVERSAL PROTOCOL)"
- *V1:* Designed a protocol spec for other systems to implement. Zero implementers existed.
- *V2 prevention:* Use REST + MCP. Don't invent protocols. Create AUP (or equivalent) only AFTER 3+ external teams ask "what's the spec for building against you?"

### AP-1.8 — "WORKFLOW ORCHESTRATION CREEP"
- *V1:* Started adding n8n-like workflow features.
- *V2 prevention:* AXIOM governs tool calls; AXIOM does NOT orchestrate them. If a customer wants orchestration, they use n8n/Temporal/Zapier and AXIOM sits in the governance call.

### AP-1.9 — "BUILD CONNECTORS INSTEAD OF PROXY MCP"
- *V1 would-have been:* Custom connectors for Slack, Gmail, Jira, Salesforce, etc. Thousands of hours chasing Zapier's 8K integrations.
- *V2 prevention:* MCP governance proxy. 2000+ MCP servers already exist. AXIOM sits in the middle. Zero custom connectors at launch.
- *Rule:* If an open standard already has N > 1000 implementations, don't build implementations. Build the governance layer between consumers and those implementations.

---

## 🔒 CATEGORY 2 — SECURITY SINS (the 12 canonical bugs)

These each got a row in the Phase 1.5 sin fix list. Every one of them must have a fix + prevention tool + test in v2.

### AP-2.1 — "TIMING ATTACK VIA `==`"
- *V1 bug:* `platform_secrets.py` used `==` for secret comparison. Timing side-channel.
- *V2 fix:* `hmac.compare_digest`. **Ruff custom rule blocks `==` on any variable named `secret`/`token`/`password`/`key`.**
- *Test:* `tests/security/test_timing.py` — verify constant-time branches.

### AP-2.2 — "SILENT EXCEPTIONS (17 `except: pass` IN SECURITY PATHS)"
- *V1 bug:* 110+ total `except: pass` blocks. 17 in security-significant paths. Production failures invisible.
- *V2 fix:* Custom ruff rule bans `except:` and `except Exception:` outside `main.py` root handler. Pre-commit blocks commit.
- *Test:* `tests/security/test_no_silent_errors.py` greps the codebase.

### AP-2.3 — "OAUTH SECRET COMMITTED TO REPO"
- *V1 bug:* Real OAuth client secret in committed `.env`.
- *V2 fix:* `.env` in `.gitignore` (verified by test). gitleaks + trufflehog pre-commit hooks. Pydantic Settings with `SecretStr`. Redaction filter in structlog.
- *Test:* gitleaks runs on every commit AND in CI on every PR.

### AP-2.4 — "STACK TRACES LEAKED IN 5XX RESPONSES"
- *V1 bug:* Python traceback in API error responses.
- *V2 fix:* Custom 500 handler returns `{"error": {"code": "internal_error", "message": "..."}}` only. No stack traces ever.
- *Test:* `tests/security/test_no_stack_traces.py` triggers 500 via malformed JSON and inspects response.

### AP-2.5 — "PASSWORDS IN LOGS"
- *V1 bug:* DEBUG-level logs captured password fields from signup requests.
- *V2 fix:* structlog redaction filter on known sensitive keys (`password`, `token`, `secret`, `api_key`).
- *Test:* `test_log_redaction.py` submits known password and inspects captured log output.

### AP-2.6 — "NO RATE LIMITING ON AUTH"
- *V1 bug:* Login / signup endpoints had zero throttling.
- *V2 fix:* slowapi + Redis. 5/min login, 10/min signup, 60/min global per-IP. Per-email counter too.
- *Test:* `test_rate_limit.py` hammers endpoint, verifies 429.

### AP-2.7 — "NO ACCOUNT LOCKOUT"
- *V1 bug:* Brute-force forever on login.
- *V2 fix:* Redis-backed, 5 fails / 15 min lockout, **per email.lower() (not per IP, to prevent IP-rotation bypass)**.
- *Test:* `test_lockout.py` fails 5 times, verifies 6th returns lockout.

### AP-2.8 — "CORS = `*`"
- *V1 risk:* Permissive CORS allowed cross-origin auth cookies.
- *V2 fix:* Allowlist only. `credentials=True` requires explicit origin match. Documented in ADR.
- *Test:* `test_cors.py` sends disallowed origin, verifies no Access-Control-Allow-Origin echo.

### AP-2.9 — "MISSING SECURITY HEADERS"
- *V1 bug:* No CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- *V2 fix:* `SecurityHeadersMiddleware` adds all six. CSP is strict: `script-src 'self'` only.
- *Test:* `test_headers.py` via curl verifies all six present.

### AP-2.10 — "UNBOUNDED REQUEST BODIES"
- *V1 bug:* No limit — 10MB+ bodies could DoS the server.
- *V2 fix:* `BodySizeLimitMiddleware` caps at 1MB. Per-route override for future file uploads.
- *Test:* `test_body_size.py` posts 2MB, verifies 413.

### AP-2.11 — "UNBOUNDED PAGINATION / QUERY STRINGS"
- *V1 bug:* `?per_page=10000` returned 10000 rows.
- *V2 fix:* Pydantic validators cap `per_page` at 100 on every list endpoint.
- *Test:* `test_pagination.py` sends 10000, verifies 422.

### AP-2.12 — "NO SSRF PROTECTION"
- *V1 risk:* User-provided URLs could hit 169.254.169.254 (AWS metadata), 127.x, 10.x, etc.
- *V2 fix:* `validate_external_url()` helper blocks private IP ranges. Full DNS rebinding protection deferred to Phase 2+ when external fetches actually occur.
- *Test:* `test_ssrf.py` submits each blocked range, verifies rejection.

### AP-2.13 — "30 METABOLISM TASKS LOGGING AT DEBUG"
- *V1 bug:* Critical observability at DEBUG level → invisible in production (where log level is INFO).
- *V2 fix:* Structured logging with levels mapped to purpose. Security events → WARNING minimum. Auth events → INFO.

### AP-2.14 — "HARDENING AS PHASE (NOT DISCIPLINE)"
- *V1 pattern:* Phase 3 was "System Hardening." Then 45-bug fix. Then another audit. Then more fixes. Still had 4 critical + 4 high at audit time.
- *V2 fix:* Hardening is a LOOP, not a phase. Re-runs after Phase 2, 2.5, 3, 3.5, 4. Same audit suite each time. **Pre-commit + CI make regression impossible (or very loud).**
- *Rule:* The moment you "finish" hardening and move on, regression starts. Hardening must be continuous.

---

## 🚧 CATEGORY 3 — PROCESS SINS (how decisions went wrong)

### AP-3.1 — "FIFTY SMALL 'JUST ONE MORE THING' DECISIONS"
- *V1 pattern:* v1 went from 10 tables to 130 tables. NOT via one bad decision. Via fifty small ones, each feeling smart at the time.
- *V2 prevention:* **Every phase prompt has a hard "Zero new endpoints / Zero new migrations / Zero scope creep" constraint with STOP triggers.** Cursor must stop and ask if any task feels feature-y.
- *Detection signal:* If you catch yourself thinking "while I'm in here, let me add X" — STOP. Write X in `ideas.md`. Finish current phase.

### AP-3.2 — "PLANNING INSTEAD OF DOING"
- *V1 pattern (observed in v2 rebuild chat too):* 3 hours in → PPT, mockups, MCP discussion, "honest thoughts" question. Zero lines of code.
- *V2 prevention:* The brutal-math check: Time today / Lines deployed / Humans who can use it. If lines=0, planning mode.
- *Rule:* Planning deliverables (PPT, mockups, architecture docs) must produce ≤ 1 day of output. If > 1 day, you're procrastinating.

### AP-3.3 — "HARDENING WITHOUT EXTERNAL AUDIT"
- *V1 pattern:* Adversarial self-review = Cursor reviewing Cursor. Misses its own blind spots.
- *V2 prevention:* Phase 1.5+ hardening loops use external audit tools (CodeQL, gitleaks, trufflehog, pip-audit, npm audit, Trivy) NOT just self-review.
- *Rule:* Any component graded by the same agent that built it is effectively ungraded.

### AP-3.4 — "RECIPE-COPYING INSTEAD OF SALVAGING"
- *V1 trap during v2 planning:* Almost transplanted "copy the pipeline + crypto" without checking if V1's ML-DSA-65 library is still on PyPI, if V1 used canonical JSON, if there are exactly 17 PI signatures.
- *V2 prevention:* Phase 1.75 V1 Salvage Recon — READ-ONLY scan before any transplant, report to human first, THREE library-alive / canonical-JSON / signature-count checks before transplant.
- *Rule:* Never transplant code without a recon report and human-verified checks.

### AP-3.5 — "FAKE COMPLETION (TESTS FAILING, STILL CLAIMED DONE)"
- *V1 pattern:* "Phase 3 complete!" reported while tests were failing.
- *V2 prevention:* Every phase prompt has Section 7 verification gates. "Done" means every gate passes — not some, all. Adversarial self-review at end of every phase. **If any gate fails, phase is not done. Fix or revert.**
- *Rule:* A phase that ships with known failures is a phase that didn't ship.

### AP-3.6 — "NO COMMIT LADDER"
- *V1 pattern:* Got pwned, only option was "reset to `d4b6304`." Lost everything between.
- *V2 prevention:* Tagged milestones form a rollback ladder: `v0.1.0-phase-1`, `v0.1.5-hardening`, `v0.1.6-cleanup`, `v0.1.75-crypto`. 30-second reset to any known-good state.

### AP-3.7 — "CONTEXT POLLUTION ACROSS PHASES"
- *V1 pattern:* Same Cursor chat used across all phases → context from Phase 2 polluted Phase 3 decisions.
- *V2 prevention:* **Fresh Cursor chat per phase.** New window, Opus 4.6, Agent ON. Phase N's context never bleeds into Phase N+1.

### AP-3.8 — "NO ADR TRAIL"
- *V1 pattern:* Decisions made, rationale lost, re-litigated in Phase 7 because nobody remembered why Phase 3 chose X.
- *V2 prevention:* `docs/decisions.md` with MADR-format ADRs. Phase 1 shipped with ADRs 1-12. Phase 1.5 adds 13-20. Every architectural decision gets an ADR. Future phases reference, don't re-litigate.

---

## 📈 CATEGORY 4 — SCOPE SINS (feature creep patterns)

### AP-4.1 — "PREMATURE ENTERPRISE FEATURES"
- *V1 bugs:*
 - SSO / SAML / OIDC built with zero enterprise customers
 - Stripe billing with 4 tiers with zero paying customers
 - Complex org hierarchy with zero multi-org customers
 - API key management UI with zero devs asking for it
- *V2 prevention:* Build enterprise feature X only when a named enterprise contact says "we'll sign when X ships." Not before.
- *Rule:* Enterprise features have "who asked" documentation. If nobody asked, they're premature.

### AP-4.2 — "42K SEED ROWS OF TEST DATA"
- *V1 bug:* 42,000 seed rows of alert rules. Demo poison — made everything slow.
- *V2 prevention:* Seed data caps: 3 agents, 5 policies, 10 sample executions. Real users generate real data.
- *Rule:* Any seed data ≥ 100 rows needs justification. Seed data is for demos, not performance testing.

### AP-4.3 — "POST-DEPLOY PHASES NOBODY ASKED FOR"
- *V1 pattern:* "Phase 11: Osmotic Data Membrane. Phase 21: Morphogenetic Interface." Named to sound deep. Solved nothing.
- *V2 prevention:* Phase names describe what a user can do after it ships. ("Phase 2: The Engine (/v1/govern returns signed receipts)"). If you can't explain in 10 words what a user gains, the phase is wrong.

### AP-4.4 — "MCP PROXY / SDK IN PHASE 1"
- *V1 would-have-been trap in v2:* Build MCP governance proxy and Python/TS SDKs at launch.
- *V2 prevention:* REST API with `tool` field ships Phase 2. MCP proxy is Phase 5 (week 2). SDK is Phase 6 (week 3). Only build these if customers ask during weeks 2-3.
- *Rule:* Integration patterns get built AFTER a user says "I want to integrate this way." Not in anticipation.

### AP-4.5 — "INTELLIGENT INJECTION DETECTION BEFORE BASIC INJECTION DETECTION"
- *V1 risk:* Build LLM-judge layered injection detection (StruQ + SecAlign + MELON) before having the 17 signature patterns wired.
- *V2 prevention:* Phase 2 = Layer 1 (Spotlighting + 17 V1 signatures). Phase 3.5 = Layer 2 (LLM judge + structured queries). Build in order.

### AP-4.6 — "FIVE NEW FEATURES RIGHT BEFORE PHASE 1 PASTE"
- *V1-in-v2 observed:* User asked for prompt injection + API key management + custom agent builder + natural language policies + v1 file review — all as Phase 1 adds, right before Phase 1 was about to paste.
- *V2 prevention:* Response must be "after Phase 1 ships, we do V1 salvage recon, then integrate these one at a time as later phases." NOT edit Phase 1.
- *Rule:* Features requested while current phase is running get written to `ideas.md`. Never into the current prompt.

### AP-4.7 — "UNIVERSAL CUSTOMER WITH ZERO CUSTOMERS"
- *V1 pattern:* Marketing copy targeted "any company using AI." Zero companies identified as customer #1.
- *V2 prevention:* Pick one beachhead vertical for first 90 days (HR/hiring, financial services, or defense). Product stays universal, selling stays specific. Expand when 5 logos signed.
- *Reference:* Every universal infrastructure winner (AWS → indie devs; Stripe → YC hackers; Slack → small tech teams; Datadog → DevOps engineers; Plaid → YC fintech) started narrow. Zero counterexamples.

---

## 🧬 CATEGORY 5 — NAMING SINS (buzzword and biology traps)

### AP-5.1 — "BIOLOGICAL METAPHOR IN CODE"
- *V1:* Metabolism, dormancy, DNA genome encoder, consciousness mesh, temporal prophecy, governance dreaming, speciation, fusion, light split.
- *V2 prevention:* Name things after what they do. `PolicyEvaluator`, not `Cortex`. `RequestQueue`, not `SpikeBus`. `CachedResult`, not `DormantState`.
- *Rule:* If the name requires a metaphor to explain, the name is wrong. Direct functional names only.

### AP-5.2 — "NAMES THAT SCARE ENTERPRISE BUYERS"
- *V1 phases:* "Osmotic Data Membrane," "Morphogenetic Interface," "Governance Dreaming."
- *V2 prevention:* Every user-facing name passes the enterprise-buyer test: "Would a CISO feel comfortable putting this in a procurement doc?" If no, rename.

### AP-5.3 — "FAKE PRECISION (SSL FOR AI AGENTS)"
- *V1 tagline:* "SSL for AI Agents." Sounds technical but SSL is literally wrong — AXIOM doesn't encrypt transport.
- *V2 prevention:* Taglines must be technically accurate AND buyer-understood. Current v2 tagline: "When your AI agent screws up and your lawyer asks what it did, AXIOM has a signed receipt." Accurate + buyer-relevant.

---

## 👤 CATEGORY 6 — CUSTOMER SINS (fictional buyers)

### AP-6.1 — "BUILDING FOR BUYERS YOU DON'T HAVE YET"
- *V1:* Built SSO before meeting an enterprise. Built 4-tier billing before a paying customer. Built SBIR-grade crypto before applying to SBIR.
- *V2 prevention:* Feature X requires either (a) named customer asking, or (b) concrete paperwork-in-progress (SBIR application drafted, enterprise pilot contract signed). Not "buyers might ask someday."

### AP-6.2 — "REFUSING TO CHOOSE A BEACHHEAD"
- *V1 and observed in v2 planning:* "Who's customer #1?" → "I want them all." This is loss aversion wearing the mask of ambition.
- *V2 prevention:* Product universal, selling specific. Beachhead pick is a 90-day commitment. Reassess at 5 logos.

### AP-6.3 — "THREE-FRONT COMPETITIVE WAR"
- *V1 observed stance:* "Compete with GaaS + complement Portkey + acquihire target for OpenAI." These contradict tactically.
- *V2 prevention:* Pick ONE positioning. Currently: "Compete with GaaS head-on with cryptographic proof wedge." All sales/marketing/proposal energy points at that one stance.

---

## 🚢 CATEGORY 7 — DEPLOYMENT SINS (never shipping)

### AP-7.1 — "NEVER DEPLOYED"
- *V1 over 6 months:* Zero production URL. Zero humans used it outside dev machines. Zero revenue.
- *V2 prevention:* **Phase 4 = deploy, by Day 7.** Seed data + Loom demo + live URL before any Phase 5+ work.
- *Rule:* Any phase that doesn't bring you closer to a live URL is suspect.

### AP-7.2 — "SHIPPING PRETTY INSTEAD OF WORKING"
- *V1 sibling-pattern risk:* Spending 3 days styling UI before backend works.
- *V2 prevention:* Phase 3 uses shadcn defaults. Ship ugly. Pretty is Phase 6+ AFTER revenue.

### AP-7.3 — "SBIR WITHOUT DEMO"
- *V1-era temptation:* Submit SBIR based on concept + slides.
- *V2 prevention:* Path A — build Phase 4 (deploy) first, submit SBIR with live demo URL. Rejection hurts for 6-12 months on future cycles. Demo is 20%+ win-rate lift.

### AP-7.4 — "CANARY DEADLOCK / BOOTSTRAP FAILURES"
- *V1:* System couldn't start due to circular bootstrap dependencies in biological intelligence layer.
- *V2 prevention:* Start simple, layered, with one-way dependencies. FastAPI + Postgres + Redis. No pre-start hooks beyond healthchecks.

### AP-7.5 — "DOCKER-COMPOSE DOWN DISASTER"
- *V1 incident:* `docker-compose down` wiped volumes → data loss.
- *V2 prevention:* Named volumes in `docker-compose.yml` persist. Documented rule: `docker compose down` is safe; `docker compose down -v` is destructive, requires explicit confirmation.

---

## 🛠️ CATEGORY 8 — TOOLING SINS (regression enablers)

### AP-8.1 — "NO PRE-COMMIT HOOKS"
- *V1 pattern:* Bad code reached `main` because nothing blocked commit.
- *V2 fix (Phase 1.5):* Pre-commit: ruff, mypy, gitleaks, trufflehog, detect-secrets, custom no-broad-except, custom no-print.

### AP-8.2 — "NO CI SECURITY PIPELINE"
- *V1 pattern:* No CodeQL, no Dependabot, no Trivy, no Dependency Review.
- *V2 fix (Phase 1.5):* 4 workflows — `ci.yml`, `codeql.yml`, `dependency-review.yml`, `dependabot.yml`. Runs on every PR.

### AP-8.3 — "NO COVERAGE GATES"
- *V1 pattern:* Security-critical files had <50% coverage; nobody noticed.
- *V2 fix (Phase 1.6):* 80% global, **100% per-file on `services/auth.py` and `middleware/*.py` as a SEPARATE CI step** (not bundled into global gate). Coverage can't silently erode.

### AP-8.4 — "NO ADR / DECISION LOG"
- *V1 pattern:* Decisions made, rationale lost, re-litigated Phase 7.
- *V2 fix:* `docs/decisions.md` with MADR ADRs. Every architectural decision gets one. Phase 2+ references, doesn't re-decide.

### AP-8.5 — "TESTS SO BRITTLE THEY GET MUTED"
- *V1 risk:* Flaky timing tests → team disables them → no regression catching.
- *V2 prevention (Phase 1.6):* Every timing-sensitive test uses `freezegun` or deterministic clocks. No flaky tests ship. The `--cov` stacking issue caught at 1.6 recon is an example of this — documented as a convention in decisions.md.

### AP-8.6 — "CURSOR REVIEWING CURSOR"
- *V1-would-have-been risk:* Self-review as only quality gate.
- *V2 prevention:* External tools as independent reviewer. Section 8 adversarial self-review is ONE of three layers, not the only one.

---

## 🧠 CATEGORY 9 — REASONING SINS (how thinking failed)

### AP-9.1 — "NO INVERSION / NO PRE-MORTEM"
- *V1 pattern:* Every phase planned forward ("what do we add?"). Never inverted ("what would cause this to fail?").
- *V2 prevention:* Every phase prompt has Section 8 Adversarial Self-Review ("how does this fail?") PLUS Pre-Mortem for Phase 2+ ("3 months later, it failed, what went wrong?").
- *Rule:* Don'ts before Dos. Anti-patterns checked FIRST, best practices SECOND.

### AP-9.2 — "NO STEELMAN OF ALTERNATIVES"
- *V1 pattern:* Picked approach, didn't steelman the opposite.
- *V2 prevention:* Every big decision gets Engine 10 (Steelman Adversary) — construct the strongest case AGAINST the recommendation. If it wins, change the recommendation.

### AP-9.3 — "NO SECOND-ORDER CASCADE"
- *V1 pattern:* Decisions made on first-order effects only. Third-order consequences surprised the team.
- *V2 prevention:* Every phase decision traced 3 levels. (Example: `--cov` stacking → doubled instrumentation → timing tests flake → false failures → muted tests → security regression.)

### AP-9.4 — "FAKE CERTAINTY"
- *V1 pattern:* Recommended approaches with high confidence that turned out wrong.
- *V2 prevention:* Engine 16 — explicit confidence levels. 90%+ = "do this"; 70-89% = "likely correct, but here's the risk"; 50-69% = "uncertain, here are alternatives"; <50% = "I don't know, here's what I need to find out."
- *Honesty example:* Rebuild-vs-strip decision — "I don't know which is faster. And neither do you. Pick one. Start." is worth more than a false confident recommendation.

### AP-9.5 — "MISSING MUNGER'S LATTICEWORK"
- *V1 pattern:* Engineering-only thinking. Didn't run decisions through Economics (incentives), Psychology (behavior), Biology (patterns), Military (terrain/timing), Physics (constraints).
- *V2 prevention:* Strategic decisions (positioning, vertical selection, SBIR timing) get multi-disciplinary lens. Convergence = high confidence; contradiction = critical trade-off to surface.

---

## 🎯 THE TOP 10 THAT WILL KILL V2 IF IGNORED

If you only internalize 10 anti-patterns from this library, these are the 10:

1. **AP-0** — Bottom-Up Build Trap (infrastructure-before-user forever)
2. **AP-3.1** — Fifty Small "Just One More Thing" Decisions
3. **AP-3.2** — Planning Instead of Doing
4. **AP-4.1** — Premature Enterprise Features
5. **AP-4.6** — Adding Features During Active Phase
6. **AP-6.1** — Building for Buyers You Don't Have Yet
7. **AP-6.2** — Refusing to Choose a Beachhead
8. **AP-7.1** — Never Deployed
9. **AP-2.14** — Hardening as Phase (not Discipline)
10. **AP-3.5** — Fake Completion (claiming done with failing tests)

**One-sentence version:** *Ship the simplest thing that works, to one real customer, through a continuous hardening loop, without adding scope, and deploy before polishing.*

---

## 📋 HOW TO USE THIS LIBRARY

**At every phase kickoff:**
- Review Category 1-4 (architectural, security, process, scope)
- Name the 3 anti-patterns most likely to attack this specific phase
- Prompt's constraints section must explicitly reject those 3

**At every phase completion:**
- Section 8 adversarial self-review cites this library
- "Did we regress any entry in Category 2 (security sins)?"
- "Did we commit any entry in Category 4 (scope sins)?"

**At every feature request during a phase:**
- Check AP-4.6. If feature came in while a phase is running, it goes to `ideas.md`, not the current prompt.

**At every architectural decision:**
- Check AP-1.x. If the decision adds enumeration entries, hierarchy depth, or new protocols, pause and justify against the beachhead test.

**At every "should I add this?" moment:**
- Check Top 10 list. If it triggers any of the 10, default is NO.

---

## 🔄 MAINTENANCE

- Append new entries as v2 reveals new traps. **Never delete entries** — institutional memory is the point.
- Each new entry follows the template: *What it was* / *V2 prevention* / *Detection signal* / *Rule*.
- Cross-reference from every phase plan file: `docs/phases/phase-N.md` cites which AP-entries the phase is guarding against.
- Review library at end of every major phase. Retroactively add any miss as a new AP-entry.

---

## 🧾 CHANGELOG

- **2026-04-16** — Initial library from V1 post-mortem, dual-agent audit, v2 rebuild planning transcript. 46 anti-patterns across 9 categories.

---

**This is your canonical institutional memory. Every v1 mistake, named so it's rejectable. Every phase from here on references this library. This is the document that stops v2 from becoming v1.**
