# Phase 8.2 — Purpose-separated keys, envelope encryption, GRACE_* env rename

**Status:** Ready to dispatch
**Branch:** `feat/key-separation`
**Commits:** one per part (five total)

---

## Why now

`services/vault.py:72` — `_encryption_key()` returns `get_signing_keys().evidence_key`.
One AES-256 key encrypts **both** receipt evidence and every user's LLM
credential. Those have different threat models and different lifetimes:

- Credential encryption wants rotation on a schedule, and immediately after any
  suspected exposure.
- Evidence encryption is bound to the audit trail. Rotating it means
  re-encrypting historical evidence, which is exactly the thing an audit trail
  should not casually rewrite.

Today you cannot rotate either without breaking the other. Worse, `crypto/vault.py`
stores ciphertext as an opaque `nonce || ciphertext` blob with **no key
identifier**, so nothing records which key encrypted which row. Rotation is not
merely awkward — it is unimplementable without decrypting everything under a
guessed key.

The database was recreated recently and holds near-zero rows. This migration
will never be cheaper.

---

## Target design

Standard envelope encryption, versioned, KMS-ready.

```
GRACE_VAULT_KEK_B64  ──(wraps)──▶  per-row DEK  ──(encrypts)──▶  credential
GRACE_EVIDENCE_KEY_B64 ─────────────────────────(encrypts)────▶  receipt evidence
```

Four properties, each earning its place:

**Per-row DEK.** Each credential gets its own random 256-bit data key. The DEK
is encrypted ("wrapped") by the KEK and stored beside the ciphertext. Rotating
the KEK then means unwrapping and re-wrapping a 32-byte DEK per row — it never
touches the credential plaintext, never needs the upstream provider, and is
fast enough to run online. This is the single decision that makes rotation a
non-event forever.

**Key identifier on every row.** `kek_id` records which KEK wrapped the DEK.
Readers dispatch on it, so old and new keys coexist during a rotation and you
can retire a key once its row count reaches zero. Without this column nothing
else here is possible.

**AAD binding.** `crypto/aes_gcm.py` already accepts `associated_data`;
`crypto/vault.py` passes `None`. Bind each ciphertext to its identity:

```
AAD = b"grace/vault/v2|" + str(vault_key_id) + "|" + str(user_id)
```

An attacker with write access to the database then cannot move a ciphertext
between rows or users — the GCM tag fails. This costs nothing and closes a real
class of attack that pure confidentiality does not.

**Purpose separation by derivation, with explicit override.** When
`GRACE_VAULT_KEK_B64` is unset, derive it:

```
HKDF-SHA256(ikm=<evidence key>, salt=None, info=b"grace/vault-kek/v1", length=32)
```

Local dev keeps working with zero new configuration, and the derived key is
still cryptographically distinct from the evidence key, so a vault compromise
does not hand over evidence decryption. Production sets an independent
`GRACE_VAULT_KEK_B64` and gets full separation. Document plainly that derivation
gives *purpose* separation, not *root* separation — the evidence key still
implies the vault KEK, which is why production overrides it.

---

## Part 1 — Crypto core

New module `services/crypto/envelope.py`. It must not import routers, models,
middleware, or `axiom.db` — `.importlinter` contract 3 keeps
`axiom.services.crypto` a leaf, and this belongs inside that boundary.

```python
@dataclass(frozen=True)
class WrappedSecret:
    kek_id: str          # fingerprint of the KEK that wrapped the DEK
    scheme: str          # "grace/vault/v2" — future schemes get a new value
    wrapped_dek: bytes    # nonce || AESGCM(KEK, dek)
    ciphertext: bytes     # nonce || AESGCM(dek, plaintext, aad)

def seal(plaintext: bytes, kek: bytes, *, kek_id: str, aad: bytes) -> WrappedSecret
def unseal(secret: WrappedSecret, kek: bytes, *, aad: bytes) -> bytes
def rewrap(secret: WrappedSecret, old_kek: bytes, new_kek: bytes, *, new_kek_id: str) -> WrappedSecret
```

`rewrap` unwraps and re-wraps the DEK only. It must never decrypt the payload —
add a test asserting the `ciphertext` field is byte-identical before and after.
That test is the guarantee that rotation stays cheap.

Key resolution goes through a small registry, `services/crypto/kek_registry.py`:

```python
def active_kek(purpose: Purpose) -> tuple[bytes, str]     # for writes
def kek_by_id(purpose: Purpose, kek_id: str) -> bytes     # for reads
```

`Purpose` is a `StrEnum` (`VAULT`, `EVIDENCE`). Reads resolve by recorded id so
a retired-but-still-referenced key still decrypts. Keep the lookup behind this
interface rather than reading settings at call sites — when `keys_kms.py` stops
being a stub, this is the one place that changes.

Also fix, while here: `crypto/vault.py`'s module-level `_seen_nonces` set grows
without bound for the process lifetime. Cap it, or drop it — a 96-bit random
nonce collision is not the risk this defends against, and an unbounded set in a
long-lived worker is.

---

## Part 2 — Migrate the vault to envelope encryption

**Schema.** Alembic migration adding to `vault_keys`:

- `kek_id TEXT NULL`
- `scheme TEXT NOT NULL DEFAULT 'legacy/v1'`
- `wrapped_dek BYTEA NULL`

Nullable and defaulted so the migration is online-safe and reversible. The
`downgrade` must actually work — write it and test it.

**Dual-read, single-write.** `services/vault.py`:

- Every read dispatches on `scheme`. `legacy/v1` → today's
  `aes_vault.decrypt(row.encrypted_key, evidence_key)`. `grace/vault/v2` →
  `envelope.unseal(...)` with the AAD above.
- Every write uses v2. No new legacy rows, ever.
- A row with `scheme='grace/vault/v2'` and a null `wrapped_dek` is corrupt —
  raise, do not fall back. Silent fallback to a legacy path is how a migration
  quietly never finishes.

**Backfill.** `axiom-keys migrate-vault` (see Part 4). Reads legacy rows,
re-seals them as v2, writes back in a transaction per row. Idempotent, resumable,
`--dry-run` first. Report a count of remaining legacy rows on completion.

---

## Part 3 — Separate the evidence key

`receipt/keys.py` keeps owning the evidence key; it stops being the vault's key.

- `SigningKeys.evidence_key` remains, used **only** by the evidence pipeline
  stage.
- `services/vault.py:_encryption_key()` is deleted. Vault key material comes
  from `kek_registry.active_kek(Purpose.VAULT)`.
- `gateway/vault.py:_kek()` — same change. It currently duplicates the same
  `get_signing_keys().evidence_key` call.
- Add a startup assertion in production: vault KEK and evidence key must not be
  byte-identical. If someone sets `GRACE_VAULT_KEK_B64` to the evidence key
  value, that is a misconfiguration and should refuse to boot, not silently
  undo this phase.

Grep for other `evidence_key` consumers before assuming there are only two.

---

## Part 4 — Rotation, tooling, runbook

A rotation path that exists only in a design document is not a rotation path.

**CLI** — extend the existing `axiom` CLI or add `axiom-keys`:

- `keys status` — per purpose: active key id, row counts by `kek_id`, oldest
  row age. This is what tells you a rotation has finished.
- `keys rotate --purpose vault --new-kek-b64 <...>` — sets the new active KEK,
  then re-wraps every row, in batches, resumable. Reports before/after counts.
- `keys migrate-vault` — the Part 2 backfill.
- `keys verify --purpose vault` — attempts an unseal of every row and reports
  failures without printing plaintext. Run after any rotation.

**Runbook** — `docs/runbooks/key-rotation.md`, covering:

- Routine rotation (schedule a cadence and name it — quarterly is defensible).
- Emergency rotation after suspected KEK exposure, including that rotating the
  KEK does **not** invalidate the upstream provider keys themselves; users must
  also roll their OpenAI/Anthropic keys, and Grace should tell them so.
- **Key backup and loss.** Losing the vault KEK means every stored credential is
  unrecoverable — recovery is "every user re-enters their key," which is
  survivable. Losing the evidence key means historical receipt evidence is
  permanently undecryptable, which for an audit product is not survivable.
  State where each key is backed up and who can retrieve it. Do not skip this
  section; it is the one that matters at 3am.
- Railway specifics: env vars are visible to anyone with project access, so
  document who that is.

---

## Part 5 — `AXIOM_*` → `GRACE_*` environment variables

Executes the deferral recorded in ADR-029, using the pattern that ADR already
specifies. Roughly 40 variables.

- Every setting in `config.py` gains `AliasChoices("GRACE_X", "AXIOM_X")` with
  the **GRACE name first** so it wins when both are set.
- New variables introduced by this phase are `GRACE_*` only. They have no legacy
  form and must not acquire one: `GRACE_VAULT_KEK_B64`, `GRACE_VAULT_KEK_ID`,
  `GRACE_EVIDENCE_KEY_B64`.
- Log a deprecation warning at startup naming each `AXIOM_*` variable still in
  use, so the eventual removal is a checklist and not an archaeology exercise.
- Update `.env.example`, `docker-compose.yml`, `DEPLOY.md`, CI workflows, and
  `scripts/lib/*.sh` to the `GRACE_*` spelling.
- `receipt/keys.py` auto-generates missing keys into `apps/backend/.env` in dev —
  it must write the `GRACE_*` names.
- Do **not** touch in this part: the `axiom` Python package, `axm_live_`
  prefixes, `X-Axiom-*` headers, container/volume names, or the `./axiom` CLI
  name. Those remain deferred per ADR-029, for the reasons stated there.

Removal of the `AXIOM_*` aliases is a later phase. Note the target in the ADR.

---

## Tests

Crypto (`tests/crypto/test_envelope.py`):

- Round trip: `unseal(seal(x)) == x`.
- Wrong KEK fails with `DecryptionError`, not a wrong plaintext.
- Wrong AAD fails — encrypt for row A, attempt decrypt as row B.
- `rewrap` leaves `ciphertext` byte-identical and the plaintext recoverable
  under the new KEK only.
- Two seals of identical plaintext produce different ciphertext (fresh DEK and
  nonce per call).
- HKDF derivation is deterministic and differs from the input key material.

Vault (`tests/test_vault_envelope.py`):

- Legacy row created under the old scheme still decrypts after the migration.
- New writes are `grace/vault/v2` with a non-null `wrapped_dek`.
- v2 row with a null `wrapped_dek` raises rather than falling back.
- Backfill is idempotent — running twice changes nothing the second time.
- Full rotation: seed rows, rotate, every credential still decrypts, all rows
  report the new `kek_id`.
- Cross-user AAD: user A's ciphertext copied onto user B's row fails to decrypt.

Config:

- `GRACE_X` wins when both spellings are set.
- `AXIOM_X` alone still resolves.
- Production with vault KEK == evidence key refuses to start.

---

## Definition of done

- No code path uses the evidence key to encrypt a credential.
- Every `vault_keys` row records the `kek_id` that wrapped its DEK.
- `keys status` reports zero legacy-scheme rows after the backfill.
- A full rotation completes on seeded data with every credential still
  decryptable, verified by `keys verify`.
- Downgrade migration tested, not just written.
- `GRACE_*` works everywhere; `AXIOM_*` still works and warns.
- Runbook exists and includes the key-loss section.
- `ruff`, `mypy --strict`, `lint-imports` (5 contracts kept), full pytest with
  ≥80% coverage.
- ADR recording: envelope + per-row DEK, AAD binding, HKDF derivation as the
  unset-default, and why production must override it.

---

## Sequencing note

Parts 1–3 are the correctness change and should land together — Part 3 alone
without Part 2's `kek_id` column leaves you unable to rotate, which is most of
the point. Part 4 is what makes the design real rather than theoretical; do not
defer it, because a rotation procedure first attempted during an incident is a
rotation procedure that fails. Part 5 is independent and can land separately if
it makes review easier.

One thing to resist: this design will invite "why not per-tenant keys too?"
Because there is one tenant. Per-tenant DEK wrapping is a natural extension of
this shape — the `Purpose` enum grows a tenant dimension and `kek_registry`
resolves per tenant — but building it now means maintaining a multi-tenant key
hierarchy for a single-tenant install. The point of this phase is that the
extension stays cheap when it is actually needed.
