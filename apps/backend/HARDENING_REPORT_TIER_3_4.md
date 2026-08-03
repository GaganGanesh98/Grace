# Crypto Hardening Report — Tier 3 (Production-Grade) & Tier 4 (Court-Admissibility)

## New modules (one sentence each)

| Module | Purpose |
|--------|---------|
| `keys.py` | Defines `KeyProvider`, `KeyMetadata`, and `KeyStatus` for pluggable key backends. |
| `keys_static.py` | Development-only file-backed keys with JSON sidecars and async `KeyProvider` methods. |
| `keys_kms.py` | Production stub for KMS/HSM-backed keys; every method raises `NotImplementedError` until ADR-026 wiring. |
| `audit.py` | Structlog-based audit for sign, verify, encrypt, key lifecycle, and TSA attempts (no secrets). |
| `timestamp.py` | RFC 3161 TSA abstraction, FreeTSA HTTP client, mock provider, and `TSA_AVAILABLE` gate on `asn1crypto`. |
| `compliance.py` | Self-assessment reports for FIPS 140-3 posture and NIST PQC readiness (informational, not certification). |
| `portable.py` | JSON-serializable verification bundles for offline cross-language receipt verification. |

## Key management architecture decision log

1. **`KeyProvider` is async** — Aligns with upcoming async governance and KMS I/O without blocking the event loop.
2. **Static keys are explicit and loud** — `StaticKeyProvider` logs a warning on construction so prod misconfiguration is visible in logs.
3. **Rotation preserves old material** — Previous keys move to `ROTATE_OUT` with `successor_key_id` so historical signatures remain verifiable.
4. **KMS is a compile-time and test-time stub** — `KMSKeyProvider` proves the interface without shipping cloud credentials or vendor SDKs in-tree.
5. **Algorithm policy lives in `AlgorithmRegistry`** — Deprecation warns on sign; revocation blocks both sign and verify with `CryptoError` on verify.

## Compliance report sample output

```
Standard: FIPS 140-3
Compliant: False

Findings:
  - OpenSSL backend: OpenSSL 3.5.6 7 Apr 2026
  - AES-256-GCM: FIPS approved
  - SHA-256: FIPS approved
  - Ed25519: Not FIPS approved (use Ed25519ph or ECDSA P-256 for FIPS)
  - ML-DSA-65 (FIPS 204): FIPS approved as of 2024

Gaps:
  - OpenSSL backend is not FIPS-validated
  - Ed25519 is not in FIPS 186-5 — FIPS requires ECDSA or EdDSA with specific parameters
  - Static file keys are not FIPS compliant for key storage

Recommendations:
  - Deploy with AWS-LC or BoringSSL FIPS module
  - Add ECDSA P-256 as FIPS fallback signer in registry
  - Use HSM or FIPS-validated KMS for production key storage

Standard: NIST PQC Migration
Compliant: True
...
```

CLI: `./axiom crypto check` runs `python -m axiom.services.crypto.compliance` from `apps/backend`.

## Test results

- **`tests/unit/test_crypto`**: **157 tests collected**; latest run **153 passed**, **4 skipped** (ML-DSA stub / optional cases). Command:  
  `cd apps/backend && uv run pytest tests/unit/test_crypto -q --no-cov --override-ini addopts=-q`
- **Full `pytest`**: The repository’s root `tests/conftest.py` autouse Redis fixture requires a reachable Redis at `REDIS_URL` (and related stack for DB-backed tests). Without Docker services, many integration tests **error** on `redis.exceptions.ConnectionError`. This is an environment constraint, not a regression in the crypto package.

## REAL vs STUBBED

| Component | Status |
|-----------|--------|
| Ed25519, AES-256-GCM, Merkle append tree, hybrid sign/verify | **REAL** (existing primitives) |
| `StaticKeyProvider` | **REAL** for local dev (files under `.axiom/keys/` or configured base dir) |
| `KMSKeyProvider` | **STUB** — raises `NotImplementedError` |
| `compliance.check_fips_140_3` / `check_nist_pqc` | **REAL** reporting; **not** a CMVP validation |
| `FreeTSAProvider` | **REAL** HTTP + ASN.1 when `asn1crypto` is installed (`TSA_AVAILABLE=True`); returns `None` on network/parse failure |
| `MockTSAProvider` | **REAL** for tests (non-cryptographic token bytes) |
| `VerificationBundle` | **REAL** JSON packaging; **not** a full verifier implementation in other languages |

## Human actions before court-admissibility or FIPS claims

- Independent **cryptographic and legal review** (e.g. NCC Group, Trail of Bits) of how receipts, timestamps, and keys are used end-to-end.
- **HSM or FIPS 140-validated KMS** for signing keys in production; replace `StaticKeyProvider`.
- **FIPS 140-3** validated OpenSSL/AWS-LC/BoringCrypto module if marketing “FIPS validated” at the module level.
- **Qualified timestamps** from a TSA under your jurisdiction’s rules; FreeTSA is suitable for **development only**.
- **Operational evidence**: retention, key ceremony documentation, and audit log shipping to tamper-evident storage.

## Notes outside crypto scope

- Full test suite health depends on **Redis/Postgres** per `tests/conftest.py`; no change was made there per sprint scope.
