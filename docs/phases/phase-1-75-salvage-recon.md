# Phase 1.75A Plan — V1 Salvage Reconnaissance

## 4.1 Scope

Read-only scan of `/home/harsh/axiom-control-center/` at Git object **`d4b6304`** (tree materialized to `/tmp/axiom-v1-d4b6304-scan` for `find`/`grep`/`wc` because V1 `HEAD` at recon time was **`b3e304a`** one commit ahead; no `git checkout` was performed on V1).

Single deliverable: `/home/harsh/AXIOM-V2/docs/v1-salvage-report.md`.

No V2 production code. No V1 modifications.

## 4.2 Execution order (strict)

1. Environment verification (Section 3) → reported in report + chat table
2. Category 1: Cryptography scan
3. Category 2: 6-Stage Pipeline scan
4. Category 3: Prompt Injection detection scan
5. Category 4: Multi-Provider API Key Management scan
6. Category 5: Policy Engine scan
7. Category 6: Tool/Connector Ecosystem scan
8. Category 7: Custom Agents scan
9. Category 8: Database Models scan
10. Category 9: Tests Worth Keeping scan (`pytest --collect-only` only)
11. Three Critical Questions (Section 6) — ML-DSA-65 library, canonical JSON, PI signature count
12. Transplant Classification (Section 7) applied to every flagged file
13. Write `/home/harsh/AXIOM-V2/docs/v1-salvage-report.md` (structure in Section 8 of Phase 1.75A prompt)
14. Adversarial Self-Review (Section 10 of prompt)
15. Commit the report + plan file to V2 `main`

## 4.3 Gates

- Step 11 must have concrete answers (PyPI JSON for `dilithium-py`; canonical JSON with file:line; PI counts with file evidence).
- Step 13 report must be ≥500 lines with ≥1 file catalogued per category.
- Step 14 adversarial review must pass all 10 checks in prompt §10.
- Step 15 commit must NOT modify any V1 file.

## 4.4 Known risks + mitigations

- [Risk] V1 codebase is ~172k Python LOC in backend subtree — scan could exceed time budget. **Mitigation:** focus on `apps/backend/app` + `apps/backend/tests`; skip `node_modules`, `.venv`, `__pycache__`.
- [Risk] `uv run pytest` in V1 may try to resolve CUDA/torch wheels. **Mitigation:** use `python3 -m pytest --collect-only` against extracted tree with user site-packages; record `uv run` disk-quota failure as environment data.
- [Risk] Anchor commit vs `HEAD` mismatch. **Mitigation:** all file reads from `git archive d4b6304` extract; `git log -1` on V1 records actual detached `HEAD` for audit.

## Completion Report

- Commit hash: **(self-referential — cannot equal the embedding commit’s SHA)**; locate with: `git log -1 --oneline -- docs/v1-salvage-report.md`
- Report LOC: 686 lines
- Files catalogued: **8** Tier 1–2 file reports + **196** table inventory rows + category scans
- Time taken: single agent session (interactive)
- Adversarial review: 10/10 passed (see report §16)
- V1 status at end: `git status` on `/home/harsh/axiom-control-center` showed **no modified tracked files**; **untracked** `apps/backend/uv.lock` present (not a recon mutation)

## What Phase 1.75B starts with

- A canonical salvage report as single source of truth
- Three critical questions answered with evidence
- Tiered transplant classification with edit lists per Tier 2 file
- Dependency graph dictating transplant order
- Security smell-test results preventing re-introduction of AP-2.x sins

## What Phase 1.75B does NOT do

- Re-scan V1 (this report is canonical)
- Change the 4-tier classification (demotions happen; promotions need re-recon)
- Transplant more than what the report names (any addition = new recon phase)
