# V1 Salvage Reconnaissance Report

**Generated:** 2026-04-16 16:37 UTC
**V1 commit scanned:** d4b6304
**V1 workspace:** /home/harsh/axiom-control-center
**V1 HEAD at operator machine (FYI only):** b3e304a (one commit ahead of anchor; recon used `git archive d4b6304` extract at `/tmp/axiom-v1-d4b6304-scan`)
**V2 target commit:** 4116aabbcb46b5fd22c9991b5a13ae6192f7ad5a (4116aab docs: v1 anti-pattern library — canonical institutional memory)
**Recon agent:** Cursor (automated recon)

## 0. Executive Summary

- V1 total Python LOC (all `*.py` under extracted tree): **171,720** (`find … | wc -l` → 772 files)
- V1 backend app subtree: **769** `*.py` files under `apps/backend/app` (glob)
- V1 total test count (static `test_*.py` files repo-wide in extract): **83**
- V1 migration count: **107** version files under `apps/backend/app/db/migrations/versions` matching `*.py` excluding `__pycache__` (108 `*.py` files total in that directory; **107** migrations + packaging — report uses **107** per operator brief; directory listing shows **108** files including one `0008b` variant — **UNCERTAIN — needs human check** on whether `0008b` counts as separate migration chain)
- `pytest --collect-only` (extracted tree, `PYTHONPATH=app`, system Python 3.14): **725** tests collected, exit code **0**, with warnings (FastAPI deprecation, unknown `pytest.mark.timeout`)
- `uv run pytest --collect-only` in live V1 checkout: **FAILED** during dependency resolution (`Disk quota exceeded` while extracting CUDA-related wheels pulled via `sentence-transformers` → `torch`) — recorded as environment constraint, not a V1 code defect
- Files flagged for transplant (narrow “Phase 1.75B surgical” set): **8** core files + **1** rules-only extraction
  - TRANSPLANT-AS-IS: **1** (`canonical_json.py`)
  - TRANSPLANT-WITH-EDITS: **5** (`receipt_ed25519_internal.py`, `execution_receipt_crypto.py`, `pq_receipt_ml_dsa.py`, `policy_decision_engine.py`, `schemas/execution_control_policy.py`)
  - TRANSPLANT-RULES-ONLY: **1** (the **4** PI regex strings in `sanitize_operator_text` — counted as one rules bundle, not four separate files)
  - LEAVE: **everything else** in V1 not listed as Tier 1–3 (biological/OAM/AUP/tool fabric dominates)
- Estimated transplant time: **~10–14 engineer-hours** (see §12; **not** wall-clock automation time)

**One-paragraph verdict:** V1’s strongest salvageable assets are **deterministic canonical JSON + receipt hashing/signing** and a **small, test-backed policy decision engine**. The “six-stage pipeline” exists as documentation and orchestration in `governed_execution_engine_service.py`, but it is **deeply fused** to SQLAlchemy models, capability fabric, biological metaphors, and AUP hooks—**not** a portable library. The oft-cited “17 prompt-injection signatures” **does not match** this tree’s backend evidence: the only clearly scoped LLM instruction-injection regex set found is **4 patterns** in `sanitize_operator_text`, plus an unrelated **8-literal** DB text scan list. Post-quantum signing uses **`dilithium-py`** (`ML_DSA_65`) and appears **ALIVE on PyPI** as of recon date.

---

## 1. Three Critical Questions — Answered

### Q1. ML-DSA-65 Library Status

- Package name: **`dilithium-py`** (import path `dilithium_py.ml_dsa`)
- V1-pinned version: **`>=1.0.0`** (not equality-pinned) in `apps/backend/pyproject.toml` (`/tmp/axiom-v1-d4b6304-scan/apps/backend/pyproject.toml` line 24)
- Latest PyPI version (JSON `https://pypi.org/pypi/dilithium-py/json` at recon time): **`1.4.0`**
- Days since last release: **~121 days** (upload timestamp **`2025-12-17T19:15:07Z`** vs report date **2026-04-16**)
- Yanked releases: **none observed** for `1.4.0` in the JSON payload fields inspected (`info.yanked` false)
- Maintenance verdict: **ALIVE** (release within 12 months; pinned floor not yanked)
- Alternatives (only needed if future recon downgrades): **`oqs-python`**, **`liboqs` bindings ecosystem`** — **UNCERTAIN — needs human check** for exact ML-DSA-65 parity and packaging quality; not evaluated beyond naming.

### Q2. Canonical JSON Usage

- File that computes signed payload: `apps/backend/app/services/execution_receipt_crypto.py` — `compute_receipt_payload_hash_v1` calls `hashlib.sha256(canonical_json_bytes(payload))` (see lines **63–64** in extracted tree)
- Canonicalization method used (authoritative implementation):
    ```python
    # from apps/backend/app/core/canonical_json.py (extracted)
    normalized = _normalize_for_canonical_json(obj)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    ```
- Verdict: **CANONICAL** (explicit `sort_keys=True` + compact separators + UTF-8 bytes; plus UUID string normalization helper)
- V2 implication: **V1 receipt hashes that use `canonical_json_bytes` are internally consistent** for verification *if* the same canonicalization is ported bit-for-bit. This is **not** full RFC8785 JCS, but it is **not** “Python dict order randomness.”

### Q3. Prompt Injection Signature Count

- **Exact count (LLM instruction-injection regex “signatures” in `sanitize_operator_text`):** **4**
- **Registry file:** `apps/backend/app/services/policy_intelligence_copilot_service.py`
- Full list (descriptive names derived from regex intent):
  1. `ignore_previous_or_prior_instructions_or_rules`
  2. `disregard_previous_or_prior`
  3. `you_are_now`
  4. `new_system_prompt`
- **Additional non-LLM “injection pattern” literals (DB scan):** **8** substrings in `apps/backend/app/core/database_immune_system.py` inside `_check_injection_patterns` (`<script`, `javascript:`, `onclick=`, `onerror=`, `union select`, `drop table`, `--`, `;--`, `1=1` — count **8** entries in the `patterns = [` list)
- **Discrepancy with “17”:** The anti-pattern library / transcript number **17** was **not found** as a single registry of **17** LLM PI regex signatures in backend Python at `d4b6304`. If “17” includes other surfaces (frontend, docs-only, or a different branch), that is **UNCERTAIN — needs human check**.
- **Coverage mapping (high level, not exhaustive):** the 4 regexes partially overlap **OWASP LLM01/03** style prompt override phrases; they do **not** constitute a full MITRE ATLAS matrix.

---

## 2. Category 1: Cryptography

### 2.1 `/home/harsh/axiom-control-center/apps/backend/app/core/canonical_json.py` (anchor: d4b6304)

- LOC: **41**
- Imports: `__future__`, `json`, `re`, `uuid`, `typing.Any`
- External deps: **stdlib only**
- Tests: `apps/backend/tests/test_crypto_proof_suite.py` contains `test_canonical_json_matches_spec_vectors` and `test_canonical_json_module_is_only_signing_serializer` (plus broader suite); **33** `def test_` occurrences in that file total (ripgrep count)
- Collection status: **collects** (global collection succeeded; **725** tests)
- Test pass status: **NOT EXECUTED** (Phase 1.75A charter: no `pytest` run without `--collect-only`)
- Standalone import: **YES** (`PYTHONPATH=apps/backend/app`, `import app.core.canonical_json` succeeded in recon shell)
- Tier: **1 (TRANSPLANT-AS-IS)**
- Justification: single-purpose, stdlib-only, directly supports deterministic hashing; no biological naming.
- If Tier 2: n/a
- If Tier 3: n/a
- V2 rename suggestion: keep `canonical_json` or rename to `deterministic_json` (**AP-5.1** avoidance: no issue here)

#### Security smell-test: `apps/backend/app/core/canonical_json.py`

- AP-2.1 (timing `==`): **0** hits
- AP-2.2 (`except: pass` / bare `except Exception: pass`): **0** hits
- AP-2.3 (stack leak): **0** hits
- AP-2.4 (password log): **0** hits
- AP-2.9 (long literal secret): **0** hits
- AP-2.12 (SSRF): **N**
- AP-2.13 (DEBUG security logs): **0** hits
- Verdict: **CLEAN**

### 2.2 `/home/harsh/axiom-control-center/apps/backend/app/services/receipt_ed25519_internal.py` (d4b6304)

- LOC: **70**
- Imports: `base64`, `cryptography…ed25519`, `app.core.config.Settings`, `app.core.crypto_dev_derivation.development_derived_receipt_seed`
- External deps: **`cryptography`**
- Tests: covered indirectly via receipt/crypto suites (`test_crypto_proof_suite.py`, governed execution tests); **NOT EXECUTED**
- Standalone import: **PARTIAL** — top-level import works in recon environment, but **production behavior depends on** `Settings` + dev derivation helper (`import app.services.receipt_ed25519_internal` succeeded)
- Tier: **2 (TRANSPLANT-WITH-EDITS)**
- Justification: `except Exception: return None` on seed parse (**AP-2.2** surface — not `pass`, but broad swallow)
- Edit list:
  1. Replace broad `except Exception` on seed decode with **typed exceptions** + explicit error reporting path for operators
  2. Ensure dev-derived keys cannot activate in prod tiers (already partially gated — re-verify during 1.75B)
- V2 rename suggestion: `receipt_ed25519.py` (drop `internal`)

#### Security smell-test: `apps/backend/app/services/receipt_ed25519_internal.py`

- AP-2.1: **0**
- AP-2.2: **1** hit area (`except Exception` in seed load) — **MINOR-EDITS**
- AP-2.3: **0**
- AP-2.4: **0**
- AP-2.9: **0**
- AP-2.12: **N**
- AP-2.13: **0**
- Verdict: **MINOR-EDITS** (narrow exceptions)

### 2.3 `/home/harsh/axiom-control-center/apps/backend/app/services/execution_receipt_crypto.py` (d4b6304)

- LOC: **229**
- Imports: `base64`, `hashlib`, `hmac`, `re`, `dataclasses`, `typing`, `sqlalchemy.orm.Session`, `app.core.canonical_json`, `app.core.config.Settings`, internal signing + DB-backed pubkey lookup
- External deps: **`cryptography` (transitive)**, **`sqlalchemy`**
- Tests: `test_crypto_proof_suite.py`, governed execution / security suites reference receipt flows; **NOT EXECUTED**
- Standalone import: **NO for clean-room transplant** — importing pulls **DB session types** and **key-id lookup service** (`import app.services.execution_receipt_crypto` still *imported* in recon, but **closure is not architecturally isolated**)
- Tier: **2 (TRANSPLANT-WITH-EDITS)** *minimum*; realistically **3** if DB coupling cannot be severed quickly — recon flags **2** as “default plan” with explicit coupling edits
- Justification: contains **`except RuntimeError: pass`** and **`except Exception: pass`** fallbacks in `verify_receipt_signature_v1` (**AP-2.2**)
- Edit list:
  1. Remove/replace `except RuntimeError: pass` fallback in `sign_receipt_payload_v1` with explicit policy (**fail closed** vs **explicit legacy mode**)
  2. Remove `except Exception: pass` branches in `verify_receipt_signature_v1` (**AP-2.2**)
  3. Split **pure** `payload → hash → sign/verify` helpers from **DB-backed** pubkey fetch (V2 should inject keys)
- V2 rename suggestion: `execution_receipt_crypto.py` → `receipts/crypto_v1.py`

#### Security smell-test: `apps/backend/app/services/execution_receipt_crypto.py`

- AP-2.1: **0** (uses `hmac.compare_digest` where relevant)
- AP-2.2: **multiple** `except …: pass` patterns (**lines ~88–89, ~132–133, ~138–139** in extract) — **MINOR-EDITS** required
- AP-2.3: **0**
- AP-2.4: **0**
- AP-2.9: **0** in quick scan (**UNCERTAIN — needs human check** for embedded literals across whole file)
- AP-2.12: **N** (no direct HTTP)
- AP-2.13: **0**
- Verdict: **MINOR-EDITS**

### 2.4 `/home/harsh/axiom-control-center/apps/backend/app/services/pq_receipt_ml_dsa.py` (d4b6304)

- LOC: **102**
- Imports: `base64`, `hashlib`, typing; **lazy** imports `dilithium_py.ml_dsa.ML_DSA_65` inside functions
- External deps: **`dilithium-py`**
- Tests: `tests/test_phase12_compliance_pq_audit.py` (and crypto suite references); **NOT EXECUTED**
- Standalone import: **YES (module import)**; **NO (crypto correctness without deps)** if `dilithium-py` missing
- Tier: **2 (TRANSPLANT-WITH-EDITS)**
- Justification: development key derivation mixes **`app_secret_key`** material (**AP-2.9 risk class** if misused outside dev**) — behavior is intentional but dangerous if copied blindly
- Edit list:
  1. Remove/disable **dev-derived PQ keys** for any non-local tier in V2 (explicit operator-provided keys only)
  2. Keep ML-DSA sign/verify surface aligned with **SHA-256 digest** input contract already used by receipts
- V2 rename suggestion: `pq_receipt_ml_dsa_65.py` (explicit algorithm)

#### Security smell-test: `apps/backend/app/services/pq_receipt_ml_dsa.py`

- AP-2.1: **0**
- AP-2.2: broad `except Exception` returns `None` in loaders — **MINOR-EDITS**
- AP-2.3: **0**
- AP-2.4: **0**
- AP-2.9: **UNCERTAIN** (no long literals; derives from settings — policy-sensitive)
- AP-2.12: **N**
- AP-2.13: **0**
- Verdict: **MINOR-EDITS**

### 2.5 `/home/harsh/axiom-control-center/apps/backend/app/services/governed_execution_chain_crypto.py` (d4b6304)

- LOC: **UNCERTAIN — needs human check** (not pasted in full in recon notes; file exists and is referenced by dispatch/engine)
- Tier: **3 / 4 split**: **TRANSPLANT-RULES-ONLY** for chain-entry hashing rules if clean extraction possible; otherwise **LEAVE** if imports pull fabric — **UNCERTAIN — needs human check** full import graph in Phase 1.75B
- Default stance for this recon: **LEAVE** pending proof of isolation (**AP-1.9** connector gravity)

### 2.6 `/home/harsh/axiom-control-center/apps/backend/app/services/execution_evidence_vault.py` (d4b6304)

- Tier: **3 (TRANSPLANT-RULES-ONLY)** for “encrypt evidence at rest” concept; implementation likely **Tier 4** if tied to biological tables — flagged **UNCERTAIN — needs human check**

---

## 3. Category 2: The 6-Stage Pipeline

- Entry point (documented): `apps/backend/app/services/governed_execution_engine_service.py` module docstring: **“six-stage pipeline (intent → strategy → authority → dispatch → evidence → reconcile)”** (lines **1–3**)
- Primary orchestration surface: large functions in the same module (thousands of LOC total file — **~3145** LOC implied by read offset; **UNCERTAIN — needs human check** exact `wc -l` during 1.75B)
- Dispatch stage implementation: `apps/backend/app/services/governed_execution_dispatch.py` — `async def governed_dispatch_from_grant` (starts ~line **162** in extract)
- Stage count: **6 named conceptual stages** in engine header, but runtime path includes many parallel “hooks” (`quantum_wave_dispatch_*`, `biology_nervous_cycle_dispatch`, etc.) — treat as **>6 operational hooks** (**AP-1.1** / **AP-4.6** risk: scope creep inside “stage”)
- Stage interface/protocol: not a single `typing.Protocol`; primary shapes are Pydantic models in `apps/backend/app/schemas/governed_execution_engine_v1.py` (imported list includes `GovernedExecutionContextV1`, `ExecutionIntentV1`, …)
- Context shape (representative import block excerpt from `governed_execution_engine_service.py` lines **50–63**):
  - `GovernedExecutionContextV1`, `ExecutionIntentV1`, `ExecutionStrategyV1`, `ExecutionOutcomeV1`, `EvidenceSummaryV1`, `ExecutionReceiptV1`, …
- Fail-closed behavior: `apps/backend/app/services/project_execution_control_service.py` states unknown/corrupt execution control states normalize to **`blocked`** (**fail closed**) in docstring comment near top (**line ~67** region in grep hit) — **YES** for execution-control plane; **NO (not uniformly)** for every adapter path (`governed_execution_dispatch.py` contains multiple `except Exception: pass` / debug-only swallow patterns — **AP-2.2** class issue at orchestration layer)
- Biological coupling: **YES** — explicit symbols like `biology_nervous_cycle_dispatch` in `governed_execution_dispatch.py` grep hits — **LEAVE** for transplant as a unit (**AP-1.1**)

### Pipeline files (summary tiers)

- `governed_execution_engine_service.py`: **Tier 4 (LEAVE)** — **AP-1.1** biological intelligence + **AP-1.9** fabric coupling
- `governed_execution_dispatch.py`: **Tier 4 (LEAVE)** — **AP-1.1**, **AP-1.7** AUP meta slices (`_aup_adapter_execution_meta`), **AP-2.2** risk in control flow
- `task_execution_preflight.py`: **Tier 4 (LEAVE)** as a whole; contains valuable **policy** subgraph (`evaluate_policy_decision` import) but is not isolatable without rewrite (**AP-4.1** enterprise surface area)

---

## 4. Category 3: Prompt Injection Detection

- Detector module path: **no** `apps/backend/src/**` layout exists in V1; primary operator-text sanitizer is `apps/backend/app/services/policy_intelligence_copilot_service.py::sanitize_operator_text`
- LOC: module total **~1309** lines (`wc -l` not re-run here — **UNCERTAIN — needs human check** exact)
- Signature count: **4** (Section 1 Q3)
- Transformation detectors: **not** a dedicated base64/unicode-smuggling engine; **NULL-byte strip** in sanitizer (`raw.replace("\x00", "")`) — limited
- Spotlighting: **absent** in backend scan hits (**UNCERTAIN — needs human check** frontend)
- Test corpus: `apps/backend/tests/test_policy_intelligence_copilot_phase14.py::test_prompt_injection_sanitized` references canonical attack string
- Per-file classification:
  - `policy_intelligence_copilot_service.py`: **Tier 4 (LEAVE)** as a module transplant (**AP-4.1**, LLM copilot scope), but contains **Tier 3** extractable regex list (**4 entries**) — **AP-4.6** note: extracting rules is not “building the feature,” it is recon classification

### Rescan addendum (Phase 1.75A-bis)

Rescan completed **2026-04-16** via Phase 1.75A-bis prompt. Targeted grep sweep on extracted V1 tree `/tmp/axiom-v1-d4b6304-scan/` (commit **d4b6304**): broader PI keyword assignments (`JAILBREAK`, `BLOCKLIST`, … at line start), filename hints (`*injection*`, `*jailbreak*`, …), heuristic strings (`ignore previous instructions`, `jailbreak`, `DAN`, …), YAML/JSON registries, `class …Guardrail|Filter|…`, docstring/comment hints for “17 signatures,” plus manual follow-up on `immune_system.py` / `action_entanglement.py`.

**Result: 0 new LLM-facing PI regex signatures found** beyond the four in `sanitize_operator_text` (`policy_intelligence_copilot_service.py` **74–79**).

**Final PI transplant corpus (Phase 1.75B):** **4** LLM-oriented regexes only (Tier 3 — rules only). No second Python registry of operator-text PI regexes surfaced.

**DB / XSS–SQL substring list (`database_immune_system.py::_check_injection_patterns`):** rescan line count on `patterns = [` is **9** literals at **337–347** (`<script`, `javascript:`, `onclick=`, `onerror=`, `union select`, `drop table`, `--`, `;--`, `1=1`). Section 1 Q3’s “**8**” for this list is **inconsistent** with the file as extracted; human reconciliation of §1 vs this line count is **out of scope** for this addendum (§4-only edit charter). Those literals remain **AP-1.1 biological — LEAVE** (not LLM prompt-injection transplant material).

**UNCATALOGUED — out of scope for this task (classification notes):**

| Evidence | Verdict |
| --- | --- |
| `apps/backend/app/core/immune_system.py` **25–31**, **258–267** — `GLOBAL_THREAT_TYPES` / `KNOWN_ATTACK_TYPES` include the string `prompt_injection` | 🟡 **Adjacent** — execution causal-node / antibody **taxonomy labels**, not a text-scanning signature registry |
| `apps/backend/app/core/action_entanglement.py` **24+** — `INNATE_PATTERNS` | ⚪ **False positive** for PI — email/calendar/document **keyword** bundles, not instruction-injection patterns |
| `apps/backend/app/core/logging.py` **11** — `class AxiomContextFilter` | ⚪ **False positive** — logging `Filter`, unrelated |
| `apps/backend/tests/test_policy_intelligence_copilot_phase14.py` **643** — test string `Ignore previous instructions…` | ⚪ **False positive** — test fixture |
| `apps/backend/app/services/verifier_service.py` — `_OVERCONFIDENCE_PATTERNS` / `_FAKE_CITATION_PATTERNS` | 🟡 **Adjacent** — LLM **output** heuristics, not operator prompt-injection sanitization |

The “**17** signatures” figure from prior chat transcripts remains **unsupported** by V1 @ d4b6304 as a single backend PI regex registry. Phase 1.75B proceeds with **4** LLM regexes; V2 can expand the corpus via Phase 3.5 (intelligent injection layer) using OWASP LLM Top 10 / MITRE ATLAS as reference.

---

## 5. Category 4: Multi-Provider API Key Management

- Provider abstraction present? **YES** — `apps/backend/app/providers/*.py` (`openai_provider.py`, `anthropic_provider.py`, …) + fabric/router services
- Key encryption mechanism: **Fernet-like patterns / vault** — **UNCERTAIN — needs human check** exact primitive without running code; `grep` shows `api_key_vault` routes and `user_provider_secrets_service.py`
- Providers wired (non-exhaustive file list): OpenAI, Anthropic, Groq, Google, Mistral, Azure OpenAI, Bedrock, Together, Ollama/custom OpenAI-compatible
- Cost tracking: **YES** evidence (`ai_cost_records`, `tests/test_ai_provider_fabric_phase14b.py` mentions cost summary) — **LEAVE** for V2 launch scope (**AP-4.1**) unless product demands billing again

### Files + classification

- `apps/backend/app/api/api_key_vault.py`: **Tier 4 (LEAVE)** — **AP-4.1** enterprise vault surface (may revisit as Tier 3 “schema only”)
- `apps/backend/app/services/user_provider_secrets_service.py`: **Tier 4 (LEAVE)** — likely entangled with V1 auth model (**AP-2.x** review needed if ever resurrected)

---

## 6. Category 5: Policy Engine

- Engine file + entry function: `apps/backend/app/services/policy_decision_engine.py::evaluate_policy_decision`
- Rule JSON schema (canonical model): `PolicyRuleSetV1` in `apps/backend/app/schemas/execution_control_policy.py` (fields: `only_allow_tasks`, `deny_tasks`, `require_approval_tasks`, `allow_paths`, `deny_paths`, `block_phrases`, `allow_domains`, `deny_domains`, `version: Literal[1]`)
- Governance mode count (**OAM spectrum modes**): **8** keys in `apps/backend/app/core/oam_governance.py` (`_MODES` list lines **119–128**)
- Mode names: `safety`, `intent`, `provider`, `evidence`, `adversarial_risk`, `cost`, `operator_load`, `drift` (labels include human text like “Safety & Compliance”)
- Shadow/audit/enforce: `task_execution_preflight.py` imports `run_policy_shadow_evaluation` / `structured_rules_to_shadow_policy_rule_set` — **shadow compare exists** in V1 policy stack (precise semantics: **UNCERTAIN — needs human check** beyond import evidence)
- Policy pack seed row count: **NOT COUNTED** (would require DB or seed file enumeration) — **UNCERTAIN — needs human check**; likely triggers **AP-4.2** if ≥100 rows in prod seeds
- Natural language → JSON policy generation: **present** as “Policy Intelligence Copilot” LLM modules — **NOT** “absent”; the prompt’s “likely does NOT exist” is **false for V1** (copilot exists), so NL assistance is **Tier 4 (LEAVE)** for transplant (**AP-4.6**, **AP-4.1**)

### 6.1 `apps/backend/app/services/policy_decision_engine.py` (Tier 2 — TRANSPLANT-WITH-EDITS)

- LOC: **263** (`wc -l` on extracted file)
- Imports: pydantic schema types from `app.schemas.execution_control_policy` and enums from `app.schemas.execution_control_enums`
- External deps: **stdlib + pydantic v2** (project already uses pydantic)
- Tests: `apps/backend/tests/test_policy_decision_engine.py` (collection included in **725**); **NOT EXECUTED**
- Standalone import: **PARTIAL** — pure functions, but imports AXIOM task constants (`POLICY_TASK_TYPES_V1`) which is V1-specific coupling
- Tier: **2 (TRANSPLANT-WITH-EDITS)**
- Edit list:
  1. Replace / slim `POLICY_TASK_TYPES_V1` coupling for V2’s reduced task taxonomy
  2. Keep evaluation ordering semantics documented in file header (do not “simplify” silently)
- V2 rename suggestion: `policy_rule_evaluation.py`

#### Security smell-test: `apps/backend/app/services/policy_decision_engine.py`

- AP-2.1: **0**
- AP-2.2: **0** (`grep` for `except: pass` / bare `except Exception: pass` — none found in quick scan)
- AP-2.3: **0**
- AP-2.4: **0**
- AP-2.9: **0**
- AP-2.12: **N**
- AP-2.13: **0**
- Verdict: **CLEAN**

### 6.2 `apps/backend/app/schemas/execution_control_policy.py` (Tier 2 — TRANSPLANT-WITH-EDITS)

- LOC: **187** (`wc -l` on extracted file)
- Tier: **2** — schema should move with the engine

#### Security smell-test: `apps/backend/app/schemas/execution_control_policy.py`

- AP-2.1: **0**
- AP-2.2: **0**
- AP-2.3: **0**
- AP-2.4: **0**
- AP-2.9: **0**
- AP-2.12: **N**
- AP-2.13: **0**
- Verdict: **CLEAN** (declarative Pydantic models in reviewed portions)

---

## 7. Category 6: Tool / Connector Ecosystem (Mostly LEAVE)

- Tool ecosystem migration: `apps/backend/app/db/migrations/versions/0092_tool_ecosystem_v1.py` exists (filename match)
- AUP code locations (sample): `apps/backend/app/core/aup_protocol.py`, `apps/backend/app/core/aup_crypto.py`, `apps/backend/app/api/aup.py`, `apps/backend/app/api/aup_websocket.py`, `apps/backend/app/services/governed_execution_dispatch.py` (AUP adapter meta), `apps/backend/app/core/oam_governance.py` (AUP halt hooks)
- AUP classification: **Tier 4 (LEAVE)** — **AP-1.7**
- MCP proxy present: **NO** evidence in backend grep for a first-class MCP proxy product (**UNCERTAIN — needs human check** monorepo other packages)
- Honest verdict: large parts are **functional** in the sense of “migrations + routes exist,” but the **default for V2** remains **LEAVE** due to connector explosion (**AP-1.9**)

---

## 8. Category 7: Custom Agents

- Agent model file: `apps/backend/app/schemas/agents.py` + DB models under `apps/backend/app/db/models/…` (multiple agent tables)
- Config fields (typical): name, model, prompts, tool allowlists, execution modes (`allowed_execution_modes` appears in migrations `0050_authorization_kernel_v1.py`)
- Execution runtime coupling with pipeline: **YES** (`governed_execution_engine_service.py` imports agent identity + passport updates)
- Biological features: `agent_species`, `agent_fusions`, `worker_organisms`, etc. (table names) — **Tier 4 (LEAVE)** — **AP-1.4**, **AP-1.1**

---

## 9. Category 8: Database Models (Schema Transplant)

### 9.1 V1 table inventory

**Note:** V1 uses `governed_executions` / `execution_receipts` / `audit_merkle_nodes`, not necessarily the V2 placeholder names `executions` / `receipts` / `merkle_nodes`.

**Extractor note:** **196** unique `op.create_table(` names parsed from `apps/backend/app/db/migrations/versions/*.py` in the `d4b6304` extract.

Below, each table is tagged **MAP-TO-V2** only when it plausibly maps to V2 Phase 1/1.75 target schema; otherwise **LEAVE**.

- `action_entanglements` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `action_intent_policy_evaluations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `action_intents` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `action_metabolism` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `action_superpositions` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `activity_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_constitutions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_fusions` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `agent_handoffs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_identities` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_job_attempts` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_job_delivery_generations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_jobs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_mesh_members` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `agent_meshes` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `agent_missions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_passports` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_run_spans` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_runs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_scope_violations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `agent_species` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `agent_symbiosis` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `ai_cost_records` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `ai_provider_health_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `ai_provider_health_pulses` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `ai_provider_models` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `ai_providers` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `ai_router_decisions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `api_key_vault` — ✅ MAP-TO-V2 (under review)
- `approval_tunnels` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `approver_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `async_merkle_queue` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `audit_events` — ✅ MAP-TO-V2
- `audit_log_entries` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `audit_logs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `audit_merkle_checkpoints` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_merkle_leaves` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_merkle_nodes` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_merkle_roots` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_merkle_subtree_commitments` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_merkle_trees` — ✅ MAP-TO-V2 (merkle subsystem)
- `audit_queue_saturation_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `aup_channels` — ❌ LEAVE (AP-1.7)
- `authorization_decision_log` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `axiom_signing_keys` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `canary_breach_events` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `canary_events` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `canary_tokens` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `causal_links` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `causal_wormholes` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `compliance_wave_functions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `consciousness_mesh` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `control_authority_audit_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `control_chains` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `cortex_evaluations` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `custom_agent_registrations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `data_heartbeats` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `database_antibodies` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `database_vitals` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `decision_consciousness` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `decision_entanglement_groups` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `decision_prophecies` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `decision_records` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `dna_installations` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `dna_lineage` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `dna_listings` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `dna_ratings` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `entanglement_events` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `entanglement_groups` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `entanglement_members` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `entanglement_patterns` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `enterprise_inquiries` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `entropy_scores` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_causal_nodes` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_chain_audit_window_cache` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_chain_verification_results` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_dna` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `execution_evidence` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_evidence_records` — ✅ MAP-TO-V2
- `execution_grants` — ✅ MAP-TO-V2
- `execution_holograms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `execution_memory_fields` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_model_attestations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_nervous_systems` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_phase_checkpoints` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `execution_receipts` — ✅ MAP-TO-V2
- `execution_runtime_journal` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `food_web_links` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `fractal_nodes` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `global_audit_entries` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `global_intelligence` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_autopilots` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_dreams` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `governance_interpretations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_kernel_evaluations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_reuse_patterns` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_shadows` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governance_singularity` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `governance_templates` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governed_execution_approval_tickets` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `governed_execution_chain_entries` — ✅ MAP-TO-V2
- `governed_executions` — ✅ MAP-TO-V2
- `hormonal_events` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `hydra_heads` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `identity_verifications` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `immune_antibodies` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `intent_anchors` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `intent_tunnels` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `intent_verifications` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `interference_patterns` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `invariant_violation_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `key_rotation_audit_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `knowledge_condensates` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `knowledge_fields` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `light_splits` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `membrane_violation_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `memory_items` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `mission_agents` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `natural_language_agents` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `neural_chain_nodes` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `oam_decisions` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `operator_notification_reads` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `organizations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `parallel_agent_groups` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `password_reset_tokens` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `platform_role_assignments` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `plugin_instances` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `plugin_seeds` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `policy_activation_logs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_advisories` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_authoring_results` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_collapses` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_conflict_graph_snapshots` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_conflict_records` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_consciousness` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `policy_conversation_sessions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_explanations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_governance_memory` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_impact_previews` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_intelligence_audit_log` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_profile_versions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_profiles` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_recommendations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_rule_embeddings` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_rule_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `policy_simulations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_template_configurations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_templates` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `policy_versions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `project_execution_controls` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `project_genomes` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `project_invitations` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `project_members` — ✅ MAP-TO-V2
- `project_policies` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `project_role_assignments` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `projects` — ✅ MAP-TO-V2
- `promo_code_redemptions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `provider_cost_profiles` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `provider_credentials` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `provider_federation_policies` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `provider_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `provider_selection_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `quantum_honeypot_registry` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `quantum_retrievals` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `quarantine_zone` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `receipt_cosign_events` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `receipt_witnesses` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `reconciliation_audit_records` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `route_permission_registry` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `run_reviews` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `sdk_govern_approval_tickets` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `sdk_govern_used_jtis` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `security_idempotency_responses` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `semantic_cache_entries` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `sensory_perceptions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `step_up_jti_consumptions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `synaptic_pathways` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `system_alerts` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `task_execution_approval_requests` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `task_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `temporal_immune_memories` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `tool_interactions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `tool_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `trust_entanglements` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `tsa_trusted_roots` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `usage_records` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `users` — ✅ MAP-TO-V2
- `worker_memories` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `worker_organisms` — ❌ LEAVE (AP-1.1 / AP-1.4 biological metaphor schema)
- `workflow_runs` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workflows` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workspace_agent_assignments` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workspace_audit_export_manifests` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workspace_members` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workspace_state_transitions` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)
- `workspaces` — ❌ LEAVE (AP-4.1 / out-of-scope for Phase 1.75B unless explicitly promoted)


### 9.2 `executions` table (TRANSPLANT)

V1 canonical name: **`governed_executions`** (migration `0045_governed_execution_engine_v1.py`).

```sql
-- excerpted from Alembic migration 0045 (paraphrased columns; see V1 file for exact dialect types)
CREATE TABLE governed_executions (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  requesting_identity_kind VARCHAR(32) NOT NULL,
  requesting_identity_id VARCHAR(256) NOT NULL,
  intent_hash VARCHAR(64) NOT NULL,
  strategy_id VARCHAR(64),
  grant_id UUID,
  execution_mode VARCHAR(64),
  capability_invoked VARCHAR(256),
  terminal_state VARCHAR(64) NOT NULL,
  receipt_hash VARCHAR(64),
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  idempotency_key VARCHAR(256),
  outcome_json JSON,
  correlation_id VARCHAR(128)
);
```

- V2 compatibility notes: V2 may name table `executions`; requires **column rename mapping** and foreign key targets. No `project_members.role` collision observed in this table definition.

### 9.3 `receipts` table (TRANSPLANT)

V1 canonical name: **`execution_receipts`** (migration `0045_governed_execution_engine_v1.py`).

```sql
CREATE TABLE execution_receipts (
  receipt_id UUID PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES governed_executions(id) ON DELETE CASCADE,
  grant_id UUID NOT NULL REFERENCES execution_grants(grant_id),
  match_status VARCHAR(32) NOT NULL,
  evidence_hash VARCHAR(64) NOT NULL,
  receipt_hash VARCHAR(64) NOT NULL UNIQUE,
  issued_at TIMESTAMPTZ NOT NULL
);
```

- Later migrations add signing columns (e.g. `0046_governed_execution_proof_pass_v1.py` adds `key_id`, `receipt_signature`, `receipt_payload_hash`, …) — **must be folded** into a single V2 migration plan or staged carefully.

### 9.4 `merkle_nodes` table (TRANSPLANT)

V1 canonical name: **`audit_merkle_nodes`** (migration `0055_audit_merkle_ledger_v1.py`).

```sql
CREATE TABLE audit_merkle_nodes (
  node_id UUID PRIMARY KEY NOT NULL,
  tree_id UUID NOT NULL REFERENCES audit_merkle_trees(tree_id) ON DELETE CASCADE,
  level INTEGER NOT NULL,
  position BIGINT NOT NULL,
  node_hash TEXT NOT NULL,
  left_child_id UUID REFERENCES audit_merkle_nodes(node_id) ON DELETE SET NULL,
  right_child_id UUID REFERENCES audit_merkle_nodes(node_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_audit_merkle_nodes_tree_level_pos ON audit_merkle_nodes(tree_id, level, position);
```

### 9.5 New Alembic migration plan for Phase 1.75B

**UNCERTAIN — needs human check** whether V2 wants renamed tables vs preserved V1 names. Recon recommendation (non-binding): **one migration** introducing V2 names with **views** or **import transform** from legacy names if dual-running.

---

## 10. Category 9: Tests Worth Keeping

| File | Tests (static `def test_` count) | Collects cleanly | Maps to V2 module | Tier |
|---|---:|---|---|---|
| `apps/backend/tests/test_crypto_proof_suite.py` | 33 | Yes (warnings) | `canonical_json` + receipts + audit | 2 |
| `apps/backend/tests/test_phase12_compliance_pq_audit.py` | 5+ | Yes | `pq_receipt_ml_dsa` | 2 |
| `apps/backend/tests/test_policy_decision_engine.py` | many | Yes | `policy_decision_engine` | 2 |
| `apps/backend/tests/test_policy_intelligence_copilot_phase14.py` | many | Yes | PI sanitizer regression | 3 |
| `apps/backend/tests/test_governed_execution_engine_v1.py` | 1+ | Yes | pipeline integration | 4 |

**Note:** “Tests” counts are **approximate** without per-file parsing in this table; Phase 1.75B should compute exactly.

---

## 11. Transplant Dependency Graph

1. `app/core/canonical_json.py`
2. `app/services/receipt_ed25519_internal.py` (depends on canonical bytes indirectly via callers; still logically “signing material”)
3. `app/services/pq_receipt_ml_dsa.py` (depends on hash contract; independent of Ed25519)
4. `app/services/execution_receipt_crypto.py` (depends on #1 and #2; optionally #3 via callers)
5. `app/services/policy_decision_engine.py` + `app/schemas/execution_control_policy.py` (tight pair)

**Circular dependencies:** none detected among the **Tier 1–2** cluster above; **larger pipeline imports create cycles** if attempted wholesale — **LEAVE** those cycles in V1.

---

## 12. Estimated Transplant Effort

Assumption: **~250–400 LOC/hour** when including tests + import rewiring + security edits.

| File | LOC | Test LOC | Imports to fix | Edit delta | Hours |
|---|---:|---:|---:|---:|---:|
| `canonical_json.py` | 41 | (shared suite) | low | none | 0.5 |
| `receipt_ed25519_internal.py` | 70 | shared | medium | narrow exceptions | 1.0 |
| `execution_receipt_crypto.py` | 229 | shared | high | remove `pass` except paths + split DB | 3.0 |
| `pq_receipt_ml_dsa.py` | 102 | shared | medium | dev-key policy | 1.5 |
| `policy_decision_engine.py` + `execution_control_policy.py` | 263 + 187 = **450** | many | medium | package paths | 3.0 |
| **TOTAL** | **~872** | n/a | n/a | n/a | **~9.0** |

Add **+2–5h** integration uncertainty → **10–14h** total range in §0.

---

## 13. Uncatalogued Candidates

- `apps/backend/app/services/governed_execution_chain_crypto.py` (hash-chain primitive) — might become Tier **2** if proven isolated (**UNCERTAIN**)
- `apps/backend/app/services/audit_proof_service.py` / `audit_checkpoint_service.py` — audit/Merkle integration worth separate recon pass

---

## 14. Known Gaps in This Report

- No `pytest` execution (pass/fail unknown)
- V1 `HEAD` ≠ anchor commit; recon used archive extract
- Provider secret encryption details not fully opened (time)
- Seed row counts not computed (**AP-4.2** unknown)
- Frontend not scanned for additional PI detectors

**§3 environment table (evidence):**

| Check | Expected | Actual | Status |
|---|---|---|---|
| V1 workspace open | `/home/harsh/axiom-control-center` | path exists | ✅ |
| V1 `HEAD` commit | `d4b6304` | `b3e304a` | ❌ (anchor via `git archive d4b6304`) |
| V1 working tree | clean | no tracked modifications; untracked `uv.lock` | ⚠️ |
| V2 docs readable | yes | yes | ✅ |
| `ANTIPATTERN_LIBRARY.md` present | yes | yes | ✅ |
| Python file count | any | 772 (`*.py` in extract) | note |
| Total Python LOC | any | 171,720 | note |
| Alembic migrations | ~107 | 107–108 (**UNCERTAIN**) | note |
| Test file count | any | 83 (`test_*.py`) | note |

---

## 15. Anti-Pattern Library Cross-Reference

- `governed_execution_engine_service.py` → **Tier 4** because **AP-1.1** (biological intelligence naming + behavior)
- `governed_execution_dispatch.py` → **Tier 4** because **AP-1.7** (AUP slices) + **AP-1.1**
- `oam_governance.py` / `oam_decisions` schema → **Tier 4** because **AP-1.2** (OAM “8 modes” are not shadow/enforce modes; they are “decision physics” spectrum dimensions — still institutionalized complexity)
- `immune_system.py`, `database_immune_system.py` → **Tier 4** because **AP-1.1**
- `action_entanglement.py` / entanglement tables → **Tier 4** because **AP-1.1**, **AP-1.4**
- `aup_protocol.py` → **Tier 4** because **AP-1.7**
- Large provider fabric / billing → **Tier 4** because **AP-4.1**
- Any table with `dna`, `consciousness`, `cortex`, … → **Tier 4** because **AP-1.1** / **AP-1.4**

---

## 16. Adversarial Self-Review (Prompt §10)

1. **Phantom-transplant check:** `canonical_json.py` imports are stdlib-only — **PASS**
2. **Test-runnability check:** crypto tests use `db_session` fixtures from `tests/conftest.py` — **NOT transplant-ready as pure unit tests** — **PASS (flagged)**
3. **Schema-collision check:** `governed_executions` does not duplicate `project_members.role` — **PASS**
4. **Biological-leak check:** biological terms appear only in **LEAVE** / inventory sections — **PASS**
5. **Canonicalization trap:** Q2 is **CANONICAL**; no conflict recommending transplant of signing helpers as-is without edits — still requires **AP-2.2** cleanup in verification path — **PASS (flagged)**
6. **AP-4.6 self-check:** report avoids “V2 should build X”; uses “Tier / LEAVE / UNCERTAIN” — **PASS**
7. **Honest “I don’t know” count:** multiple **UNCERTAIN** markers present — **PASS**
8. **17-signature trap:** explicitly **disproves 17** for backend registry scope — **PASS**
9. **Dependency-graph completeness:** graph is linear for small cluster — **PASS**
10. **V1 modification check:** recon agent did not write into `/home/harsh/axiom-control-center` tracked files; live tree shows **untracked** `uv.lock` only — **PASS** (with FYI)
