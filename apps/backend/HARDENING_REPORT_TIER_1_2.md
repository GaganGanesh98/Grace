# Crypto Hardening Report — Tier 1 & 2

## Summary

This sprint hardens `src/axiom/services/crypto/` for timing-safe comparisons on digests and roots, strict input validation (`validate_bytes`), memory scrubbing of raw signing keys after use, AES-GCM in-process nonce collision detection, a typed exception hierarchy, and expanded tests (KATs, Hypothesis fuzz, malformed-input parametrization).

## New modules

| File | Role |
|------|------|
| `_util.py` | `constant_time_compare`, `zero_memory` (ctypes `memset`), `validate_bytes` |
| `exceptions.py` | `CryptoError`, `CryptoInputError`, `SignatureError`, `VerificationError`, `DecryptionError`, `KeyError_`, `AlgorithmNotFoundError`, `NonceReuseError` |

`KeyError_` is intentionally spelled per spec to avoid shadowing the builtin `KeyError` (Ruff `N801`/`N818` suppressed on that class).

## Per-module changes

### `ed25519.py`

- Raw and PEM signing paths scrub PEM bytes or raw 32-byte key material in a `finally` block after signing.
- `sign` / `verify` validate message length (non-empty), raw key lengths (32 bytes), raw signature length (64 bytes) where applicable.
- PEM load/sign failures are mapped to `CryptoInputError` or `SignatureError` instead of leaking `ValueError` from the library.
- Removed signature-failure logging that could encourage log-driven probing; verification still returns `False` for invalid cryptographic proofs when inputs are well-formed.
- Invalid **types** or **lengths** for raw verification raise `CryptoInputError` (callers that need strict bool-only behavior should catch `CryptoInputError` and treat as failure—see “Edge cases” below).
- `stable_key_id` raises `CryptoInputError` for invalid PEM or non-Ed25519 keys (replacing bare `TypeError`/`ValueError`).
- `__all__`: `Ed25519KeyPair`, `generate_keypair`, `sign`, `stable_key_id`, `verify`.

### `ml_dsa_65.py`

- Validates FIPS-204-sized keys and signatures (`4032` / `1952` / `3309` bytes for the bundled `pqcrypto` backend).
- `generate_keypair` / unavailable backend: `NotImplementedError` replaced with `KeyError_` carrying the same operational message.
- `sign` scrubs a `bytearray` copy of the secret key; library failures become `SignatureError`.
- `verify` validates lengths then preserves “return `False` for invalid signatures” for well-formed inputs.

### `hybrid.py`

- Validates Ed25519 raw key length always; ML-DSA secret length when `ML_DSA_AVAILABLE`.
- ML-DSA stub mode unchanged: empty `ml_dsa_sig` when the backend is missing; warnings are generic (no secrets).
- `hybrid_verify` validates Ed25519 fields strictly; ML-DSA branch enforces expected ML-DSA signature length before calling `ml_dsa_65.verify`.

### `merkle.py`

- `build_tree` rejects empty leaf bytes.
- Root / hash equality uses `constant_time_compare` or `hmac.compare_digest` where digests are compared.
- Leaf-prefix equality for consistency proofs uses per-leaf `constant_time_compare` on equal-length data.
- `MerkleTree.verify_proof` uses `constant_time_compare` on the proof magic prefix.
- Inclusion/consistency verification validates root lengths and raises `CryptoInputError` when length rules fail (instead of silent `False` for those specific errors).
- `__all__` lists public symbols.

### `vault.py`

- `encrypt` / `decrypt` use `validate_bytes`; decrypt requires at least 28 bytes (12-byte nonce + 16-byte tag minimum).
- Module-level `_seen_nonces` tracks 12-byte nonces for the process lifetime; duplicate nonces raise `NonceReuseError` (RNG failure guard, not a cross-session anti-replay mechanism—documented in code).
- `InvalidTag` and other AEAD failures map to `DecryptionError`; encryption failures from the AEAD layer map to `CryptoInputError`.
- Re-exports `CryptoInputError`, `DecryptionError`, `NonceReuseError` for ergonomic `from axiom.services.crypto import vault` usage.

### `registry.py`

- Unknown algorithms raise `AlgorithmNotFoundError` (subclass of `CryptoError`) instead of `KeyError`.
- Algorithm names must be non-empty strings; otherwise `CryptoInputError`.

## Test updates (existing crypto tests only)

- `tests/unit/test_crypto/test_vault.py`: expectations updated for `DecryptionError` / `CryptoInputError`.
- `tests/unit/test_crypto/test_registry.py`: `AlgorithmNotFoundError`.
- `tests/unit/test_crypto/test_ml_dsa_65.py`: `KeyError_` for unavailable backend; stub `verify` uses correctly sized dummy key material.
- `tests/crypto/test_ed25519.py`, `tests/crypto/test_crypto_coverage.py`: `CryptoInputError` where validation now raises.
- `tests/crypto/test_properties.py`: Hypothesis Merkle strategies use `min_size=1` for leaf bytes (aligned with non-empty leaf policy).

## New tests

| File | Content |
|------|---------|
| `test_kats.py` | RFC 8032 Ed25519 vectors 2 & 3 (exact signatures); vector 1 documented as rejected (empty message policy); SHA-256 empty/`abc` digests; AES-256-GCM all-zero key/nonce KAT via `vault.decrypt` |
| `test_fuzz.py` | Hypothesis round-trips and tamper tests for Ed25519, append Merkle tree, vault, hybrid |
| `test_malformed_inputs.py` | Parametrized garbage inputs; registry / Merkle / hybrid edge cases |

## Test run (local)

Command used in this environment (parent `tests/conftest.py` requires Redis; `--noconftest` avoids that for `tests/crypto/`):

```bash
cd apps/backend && uv run pytest --no-cov --noconftest tests/unit/test_crypto/ tests/crypto/
```

Result: **224 passed**, **4 skipped** (ML-DSA stub tests skipped when the real backend is loaded).

Hypothesis settings match the spec (`max_examples` 200–500 per test). Full-repo `uv run pytest` with default coverage was not completed here because Redis/DB fixtures were unavailable; CI should run the full matrix.

## Edge cases and decisions

1. **RFC 8032 TEST 1 (empty message)**  
   The API requires a non-empty message for `sign`. KAT documents rejection via `CryptoInputError` rather than matching the empty-message signature.

2. **`ed25519.verify` and exceptions**  
   Malformed types or incorrect byte lengths now raise `CryptoInputError`. HTTP or pipeline callers that assumed “always bool” may need `except CryptoInputError` and to treat it as an invalid signature. This is noted for `routers/verify.py` and similar—**not changed** in this sprint per scope rules.

3. **Merkle empty leaves**  
   Append-tree leaves and `build_tree` leaves must be non-empty; empty `b""` is rejected.

4. **Hypothesis + `build_tree`**  
   Existing property tests were updated to avoid generating empty leaf bytes.

5. **`==` remaining in crypto**  
   Intentional uses remain for integer logic, empty-tree checks, and string backend names (`"pqcrypto"`). Secret-dependent byte comparisons use `constant_time_compare` or `hmac.compare_digest`.

## Ruff

`ruff check` and `ruff format` were run on `src/axiom/services/crypto/` and `tests/unit/test_crypto/` (and modified files under `tests/crypto/`).

## Deliverables checklist

- [x] `_util.py`, `exceptions.py`
- [x] Hardened: `ed25519`, `ml_dsa_65`, `hybrid`, `merkle`, `vault`, `registry`
- [x] `test_kats.py`, `test_fuzz.py`, `test_malformed_inputs.py`
- [x] `HARDENING_REPORT_TIER_1_2.md` (this file)

No git commit performed (human review pending).
