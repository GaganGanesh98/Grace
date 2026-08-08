# Runbook — Key rotation, backup, and loss

Covers the two AES-256 keys Grace holds. They are not interchangeable and the
consequences of losing them are not comparable, so read the
[Backup and loss](#backup-and-loss) section before you need it.

| Key | Env var | Protects | Rotatable |
| --- | --- | --- | --- |
| Vault KEK | `GRACE_VAULT_KEK_B64` | Wraps the per-row DEK for every stored credential | Yes — online, any time |
| Evidence key | `GRACE_EVIDENCE_KEY_B64` | Encrypts receipt evidence in the audit trail | Not casually — see below |

Related: `apps/backend/src/axiom/services/crypto/kek_registry.py`,
`services/crypto/envelope.py`, ADR-030 in `docs/decisions.md`.

---

## How the vault is encrypted

Each credential gets its own random 256-bit data key (DEK). The DEK encrypts the
credential; the KEK only ever wraps the DEK:

```
GRACE_VAULT_KEK_B64  ──(wraps)──▶  per-row DEK  ──(encrypts)──▶  credential
```

Rotating the KEK therefore means unwrapping and re-wrapping 32 bytes per row. It
never touches the credential plaintext, never contacts the upstream provider, and
is fast enough to run against a live system.

Every row records `kek_id`, so old and new keys coexist during a rotation and
readers dispatch on what the row actually says. That is what makes a rotation
interruptible: stop it halfway and the database is still consistent.

If `GRACE_VAULT_KEK_B64` is unset, the KEK is derived from the evidence key:

```
HKDF-SHA256(ikm=<evidence key>, salt=None, info=b"grace/vault-kek/v1", length=32)
```

**Derivation gives purpose separation, not root separation.** The derived key is
cryptographically distinct — a vault compromise does not hand over evidence
decryption — but the evidence key still *implies* the vault KEK. That is fine for
local dev and not fine for production. Production sets `GRACE_VAULT_KEK_B64`
explicitly. Setting it equal to the evidence key refuses to boot.

---

## Cadence

- **Routine vault KEK rotation: quarterly.** First business week of Jan / Apr /
  Jul / Oct. It is cheap; the reason to schedule it is to keep the procedure
  exercised, not because the key is expected to be weak.
- **Evidence key: not on a schedule.** Rotating it means re-encrypting historical
  evidence, which is exactly what an audit trail should not casually rewrite. It
  rotates only in response to a confirmed compromise, as a deliberate project.
- **After any suspected exposure: immediately**, and see
  [Emergency rotation](#emergency-rotation-after-suspected-exposure) — the KEK is
  not the only thing that has to change.

---

## Routine vault KEK rotation

Roughly 15 minutes plus verification. No downtime.

### 1. Check the starting state

```bash
./axiom keys status
```

Note the active `kek_id` and the row counts. If any rows are on `legacy/v1`,
finish the backfill first (see [Backfill](#backfill-legacy-rows) below) — rotation
only touches envelope rows.

### 2. Generate the new KEK

```bash
openssl rand -base64 32
```

Keep this in your hand for the next two steps; store it in the secret manager
before you use it (see [Backup and loss](#backup-and-loss)).

### 3. Make the new key active, keep the old one readable

Set both, then restart the API, gateway, and worker:

```
GRACE_VAULT_KEK_B64=<new key>
GRACE_VAULT_KEK_PREVIOUS_B64=<old key>
```

Order matters. New writes start using the new key immediately; existing rows are
still readable because their `kek_id` resolves through
`GRACE_VAULT_KEK_PREVIOUS_B64`. Doing this the other way round — rotating rows
before the config knows the new key — leaves rows nothing can read.

Confirm the running processes agree:

```bash
./axiom keys status     # active kek_id should be the new one
```

### 4. Dry run, then re-wrap

```bash
./axiom keys rotate --purpose vault --new-kek-b64 <new key>
./axiom keys rotate --purpose vault --new-kek-b64 <new key> --apply
```

The dry run reports what would change. `--apply` commits per row, so an
interrupted run resumes by being run again — rows already on the new `kek_id`
are skipped.

### 5. Verify

```bash
./axiom keys verify --purpose vault
./axiom keys status
```

`verify` attempts an unseal of every row and reports failures without printing
plaintext. A non-zero exit means stop and investigate; do not proceed to step 6.
`status` should show every row under the new `kek_id`.

### 6. Retire the old key

Only once `status` shows zero rows on the old `kek_id`:

```
GRACE_VAULT_KEK_PREVIOUS_B64=      # cleared
```

Restart, run `./axiom keys verify` once more, and keep the old key in the secret
manager (marked retired) for one rotation cycle in case a restore from an older
database backup is needed.

### If something goes wrong mid-rotation

Nothing is lost as long as both keys remain configured. Rows carry the id of the
key that wrapped them, so a half-rotated table is a supported state. Re-run
`rotate --apply`, or leave it — the system works either way.

---

## Backfill legacy rows

Rows written before Phase 8.2 are `legacy/v1`: encrypted directly under the
evidence key, with no key identifier. They are readable but not rotatable.

```bash
./axiom keys migrate-vault              # dry run
./axiom keys migrate-vault --apply
./axiom keys status                     # expect: "No legacy-scheme rows"
```

Idempotent and resumable. Run it until `status` reports zero legacy rows; until
then, the evidence key is still needed to read part of the vault, which is the
thing this phase exists to end.

---

## Emergency rotation after suspected exposure

Assume the vault KEK is exposed — leaked env var, compromised host, ex-employee
with Railway access.

1. **Rotate the KEK immediately** using the routine procedure above. Skip the
   change window; it is online and reversible.
2. **Understand what this does not fix.** Rotating the KEK re-wraps the DEKs. It
   does **not** invalidate the provider credentials themselves. If an attacker
   decrypted a stored OpenAI key before you rotated, that key still works for
   them.
3. **Tell users to roll their provider keys.** Every affected user must revoke and
   re-issue their OpenAI / Anthropic / Google / Groq / xAI credentials at the
   provider and re-enter them in Grace. Grace cannot do this for them, and a
   rotation notice that omits this step gives false reassurance.
4. **Rotate the evidence key only if it is also implicated.** If
   `GRACE_VAULT_KEK_B64` was never set, the vault KEK was derived from the
   evidence key — so an exposed *vault* KEK does not imply an exposed evidence
   key, but an exposed *evidence* key implies both. In that case treat it as an
   evidence-key incident, which is a larger piece of work: historical receipt
   evidence must be re-encrypted, and that changes the audit trail.
5. **Record the rotation.** Set `AXIOM_KEY_ROTATION_DATE` / `GRACE_KEY_ROTATION_DATE`
   so the Command Center shows it.

---

## Backup and loss

This is the section that matters at 3am. The two keys fail very differently.

### Losing the vault KEK

Every stored credential becomes unrecoverable. Recovery is "every user re-enters
their provider key" — annoying, visible, and survivable. No audit data is lost.

### Losing the evidence key

Historical receipt evidence becomes permanently undecryptable. For a product
whose entire claim is a verifiable audit trail, this is not survivable: the
receipts remain, their signatures still verify, but the evidence they attest to
can no longer be opened. **There is no recovery path.** Back this key up first
and check it more often than you think you need to.

### Where the keys live

Fill this in for your deployment and keep it current — an out-of-date entry here
is worse than an empty one:

| | Primary | Backup | Who can retrieve it |
| --- | --- | --- | --- |
| `GRACE_VAULT_KEK_B64` | Railway project env | _TODO: secret manager + path_ | _TODO: named people_ |
| `GRACE_EVIDENCE_KEY_B64` | Railway project env | _TODO: offline copy, sealed_ | _TODO: named people_ |

Verify restorability, not just existence: once per quarter, retrieve both keys
from backup and confirm they base64-decode to 32 bytes and match the running
`kek_id` values reported by `./axiom keys status`.

### Railway specifics

Railway environment variables are visible in plaintext to **anyone with project
access**, and there is no per-variable access control. That means:

- The set of people who can read the vault KEK is exactly the set of people with
  Railway project access. Enumerate them here and review it whenever someone
  joins or leaves: _TODO: named people_.
- Removing someone's Railway access does not rotate the key they already saw.
  Treat an offboarding as an exposure event and run the emergency procedure.
- Do not paste key material into deploy logs, PR descriptions, or chat. The CLI
  in this runbook never prints key material or credential plaintext; keep it that
  way.

---

## Local development

No configuration needed. With `GRACE_VAULT_KEK_B64` unset the KEK is derived from
the evidence key, which `receipt/keys.py` auto-generates into
`apps/backend/.env` on first run.

If you regenerate the dev evidence key, previously stored dev credentials become
unreadable — expected, and the reason `./axiom keys verify` may report failures on
an old dev database. Delete the rows or re-add the credentials.
