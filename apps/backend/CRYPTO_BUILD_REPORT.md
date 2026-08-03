# Phase 1.75B — Cryptographic core build report

## What was built

Under `src/axiom/services/crypto/`:

| Module | Purpose |
|--------|---------|
| `__init__.py` | Empty package marker (per spec). |
| `ed25519.py` | Extended with RFC 8032 **raw 32-byte** keys: `generate_keypair(raw=True)`, and `sign` / `verify` overloads so `(message, private_key)` and `(message, signature, public_key)` use raw bytes while the existing PEM-based API remains the default (`generate_keypair()`, `sign(SecretStr, …)`, `verify(str, …)`). |
| `ml_dsa_65.py` | ML-DSA-65 via **liboqs** (`oqs` / `liboqs-python`) when importable; otherwise a **stub** with `ML_DSA_AVAILABLE: bool` and `NotImplementedError` on `generate_keypair` / `sign` (message matches requested install hint). |
| `hybrid.py` | `HybridSignature` dataclass (`ed25519_sig`, `ml_dsa_sig`), `hybrid_sign` / `hybrid_verify` per ADR-022; stub mode uses empty `ml_dsa_sig` and warning logs when ML-DSA is unavailable. |
| `merkle.py` | RFC 6962 snapshot type renamed to `MerkleSnapshot` (returned by `build_tree`); new **`MerkleTree`** class: append-only leaves, SHA-256 leaf digests, paired levels with odd duplicate, `get_proof` returns a magic-prefixed proof list so `verify_proof(leaf_hash, proof, root)` can recover index and leaf count. |
| `vault.py` | AES-256-GCM: 12-byte random nonce prepended to ciphertext+tag. |
| `registry.py` | `AlgorithmRegistry` with `get_signer`, `get_verifier`, `get_encryptor`, and `get_hasher` (for `sha-256`). |

**Leaf-module rule:** New code only imports standard/third-party libraries and other `axiom.services.crypto` modules (no routers, DB, config).

## Dependencies

- Added explicit **`cryptography>=43.0.0`** to `pyproject.toml` (was already pulled transitively; now declared).
- ML-DSA: optional **`liboqs-python`** / **`oqs`** — not added as a hard dependency; install in environments that need real ML-DSA-65.

## Tests

- New tests live under `tests/unit/test_crypto/`.
- **`tests/unit/test_crypto/conftest.py`** overrides the suite-wide autouse Redis reset so these pure crypto tests do not require Redis (only for tests in this directory).
- **Pytest module name clash:** Existing tests already use `tests/crypto/test_ed25519.py` and `tests/crypto/test_merkle.py`. Duplicate basenames under `tests/unit/test_crypto/` break collection, so Phase 1.75B tests use **`test_ed25519_primitives.py`** and **`test_merkle_append.py`** instead of those exact names.

### Commands run (this workspace)

| Command | Result |
|---------|--------|
| `uv run ruff check src/axiom/services/crypto tests/unit/test_crypto` | Pass |
| `uv run ruff format src/axiom/services/crypto tests/unit/test_crypto` | Pass |
| `uv run pytest tests/crypto tests/unit/test_crypto --no-cov` | **108 tests collected**, **107 passed**, **1 skipped** (`test_partial_ml_signature_fails` when ML-DSA not installed). Redis was available for `tests/crypto/*` (autouse fixture). |

Full `uv run pytest` (entire backend) was **not** re-run to green here: it depends on the project’s configured Postgres (including `uuidv7()` and extensions) and Redis, matching the developer/CI stack described in the repo. Crypto-related folders above were executed successfully with `--no-cov`.

## ML-DSA-65 status

- **`ML_DSA_AVAILABLE` is false** when `oqs` is not installed (this environment).
- With **`liboqs-python`** installed and a working `oqs.Signature("ML-DSA-65")` (or fallback name `ML_DSA_65` / `Dilithium3`), the module uses the real signer/verifier.

## Design notes

- **Ed25519 API:** Legacy PEM callers are unchanged. Raw RFC 8032 uses `generate_keypair(raw=True)` and `sign(message_bytes, private_key_bytes)` / `verify(message_bytes, signature_bytes, public_key_bytes)` to avoid breaking existing `sign(private_key_pem, message)` call order.
- **Merkle:** RFC 6962 helpers are unchanged in behavior; only the snapshot type was renamed to `MerkleSnapshot` so the Phase 1.75B **`MerkleTree`** class name could be used for the append-only tree.
- **Registry:** `sha-256` is exposed via **`get_hasher("sha-256")`** (not `get_signer`), since it is a hash primitive.

## Issues / follow-ups

- Install **`liboqs-python`** to exercise real ML-DSA paths and unskip hybrid partial-signature tests.
- Confirm the **`oqs` Python API** (`import_secret_key`, `verify` argument order) against your installed liboqs version when enabling ML-DSA in production.
- Run full **`uv run pytest`** in an environment with the same Postgres and Redis as `apps/backend/.env` to satisfy the global coverage gate (`--cov-fail-under=80`).
