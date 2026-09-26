"""Resolution of key-encryption keys by purpose (Phase 8.2).

Two purposes, two threat models:

``EVIDENCE``
    Bound to the audit trail. Rotating it means re-encrypting historical
    evidence, which is exactly what an audit trail should not casually rewrite.

``VAULT``
    Wraps per-row DEKs for user credentials. Wants rotation on a schedule and
    immediately after any suspected exposure.

When ``GRACE_VAULT_KEK_B64`` is unset the vault KEK is *derived* from the
evidence key:

    HKDF-SHA256(ikm=<evidence key>, salt=None, info=b"grace/vault-kek/v1", 32)

Local dev then keeps working with zero new configuration, and the derived key is
still cryptographically distinct from the evidence key, so a vault compromise
does not hand over evidence decryption. Note plainly what this does and does not
buy: derivation gives *purpose* separation, not *root* separation — the evidence
key still implies the vault KEK. Production sets an independent
``GRACE_VAULT_KEK_B64`` and gets full separation; :func:`assert_purpose_separation`
refuses to boot if the two are byte-identical.

Reads resolve by the ``kek_id`` recorded on the row, so a retired-but-still
referenced key still decrypts. Writes always use the active key. Keeping both
behind this interface is what lets ``keys_kms.py`` stop being a stub without
touching a single call site.

This module is a leaf (``.importlinter`` contract 3), which is why the evidence
key arrives through :func:`set_evidence_key_provider` rather than by importing
``axiom.services.receipt.keys``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import threading
from collections.abc import Callable
from enum import StrEnum

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from axiom.config import get_settings

from ._util import constant_time_compare
from .envelope import kek_fingerprint
from .exceptions import CryptoInputError, KeyError_

__all__ = [
    "Purpose",
    "active_kek",
    "assert_purpose_separation",
    "derive_vault_kek",
    "kek_by_id",
    "known_kek_ids",
    "reset_for_tests",
    "set_evidence_key_provider",
]

VAULT_KEK_HKDF_INFO = b"grace/vault-kek/v1"
_KEK_LEN = 32


class Purpose(StrEnum):
    VAULT = "vault"
    EVIDENCE = "evidence"


EvidenceKeyProvider = Callable[[], bytes]

_provider_lock = threading.Lock()
_evidence_provider: EvidenceKeyProvider | None = None


def set_evidence_key_provider(provider: EvidenceKeyProvider) -> None:
    """Register the source of the evidence key.

    ``axiom.services.receipt.keys`` calls this on import, so any process that
    loads the app gets lazy resolution including dev auto-generation.
    """
    global _evidence_provider
    with _provider_lock:
        _evidence_provider = provider


def reset_for_tests() -> None:
    """Drop the registered provider so a test can install its own."""
    global _evidence_provider
    with _provider_lock:
        _evidence_provider = None


def _b64_to_key(value: str, name: str) -> bytes:
    try:
        raw = base64.b64decode(value.strip().encode("ascii"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CryptoInputError(f"{name} is not valid base64") from exc
    if len(raw) != _KEK_LEN:
        raise CryptoInputError(f"{name} must decode to {_KEK_LEN} bytes, got {len(raw)}")
    return raw


def _evidence_key() -> bytes:
    provider = _evidence_provider
    if provider is not None:
        return provider()
    raw = getattr(get_settings(), "axiom_evidence_key_b64", None)
    if raw is None:
        raise KeyError_(
            "No evidence key available. Set GRACE_EVIDENCE_KEY_B64, or import "
            "axiom.services.receipt.keys so it can register a provider.",
        )
    return _b64_to_key(raw.get_secret_value(), "GRACE_EVIDENCE_KEY_B64")


def derive_vault_kek(evidence_key: bytes) -> bytes:
    """HKDF-SHA256 the vault KEK out of the evidence key. Deterministic."""
    if len(evidence_key) != _KEK_LEN:
        raise CryptoInputError(f"evidence key must be {_KEK_LEN} bytes")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEK_LEN,
        salt=None,
        info=VAULT_KEK_HKDF_INFO,
    )
    return hkdf.derive(evidence_key)


def _explicit_vault_kek() -> tuple[bytes, str] | None:
    settings = get_settings()
    raw = getattr(settings, "grace_vault_kek_b64", None)
    if raw is None:
        return None
    key = _b64_to_key(raw.get_secret_value(), "GRACE_VAULT_KEK_B64")
    configured_id = (getattr(settings, "grace_vault_kek_id", None) or "").strip()
    return key, configured_id or kek_fingerprint(key)


def _previous_vault_keks() -> list[tuple[bytes, str]]:
    """Retired KEKs kept readable until their row count reaches zero.

    Comma-separated base64 in ``GRACE_VAULT_KEK_PREVIOUS_B64``. Without this a
    rotation would have to complete atomically, which it cannot.
    """
    raw = (getattr(get_settings(), "grace_vault_kek_previous_b64", "") or "").strip()
    if not raw:
        return []
    out: list[tuple[bytes, str]] = []
    for i, part in enumerate(raw.split(",")):
        chunk = part.strip()
        if not chunk:
            continue
        key = _b64_to_key(chunk, f"GRACE_VAULT_KEK_PREVIOUS_B64[{i}]")
        out.append((key, kek_fingerprint(key)))
    return out


def _vault_candidates() -> list[tuple[bytes, str]]:
    """Active key first, then the derived key, then retired keys.

    The derived key stays resolvable even once an explicit KEK is configured:
    rows sealed in dev before the override was set must still open.
    """
    candidates: list[tuple[bytes, str]] = []
    explicit = _explicit_vault_kek()
    if explicit is not None:
        candidates.append(explicit)
    derived = derive_vault_kek(_evidence_key())
    candidates.append((derived, kek_fingerprint(derived)))
    candidates.extend(_previous_vault_keks())
    return candidates


def _evidence_candidates() -> list[tuple[bytes, str]]:
    key = _evidence_key()
    return [(key, hashlib.sha256(key).hexdigest())]


def _candidates(purpose: Purpose) -> list[tuple[bytes, str]]:
    if purpose is Purpose.VAULT:
        return _vault_candidates()
    return _evidence_candidates()


def active_kek(purpose: Purpose) -> tuple[bytes, str]:
    """Return ``(key, kek_id)`` for new writes."""
    return _candidates(purpose)[0]


def kek_by_id(purpose: Purpose, kek_id: str) -> bytes:
    """Return the key recorded as ``kek_id``, or raise.

    Raising rather than falling back to the active key is deliberate: a row we
    cannot attribute to a known key is a fact worth surfacing, not something to
    paper over with a guess.
    """
    wanted = kek_id.strip()
    for key, candidate_id in _candidates(purpose):
        if candidate_id == wanted:
            return key
    raise KeyError_(
        f"No {purpose.value} KEK registered for kek_id {wanted!r}. "
        "Add it to GRACE_VAULT_KEK_PREVIOUS_B64 if it was retired.",
    )


def known_kek_ids(purpose: Purpose) -> list[str]:
    """All resolvable key ids for this purpose, active first. For ``keys status``."""
    return [kek_id for _, kek_id in _candidates(purpose)]


def assert_purpose_separation() -> None:
    """Refuse a configuration where the vault KEK *is* the evidence key.

    Setting ``GRACE_VAULT_KEK_B64`` to the evidence key value silently undoes
    this phase, so it is a startup failure rather than a warning.
    """
    explicit = _explicit_vault_kek()
    if explicit is None:
        return
    if constant_time_compare(explicit[0], _evidence_key()):
        raise KeyError_(
            "GRACE_VAULT_KEK_B64 is byte-identical to the evidence key. "
            "Purpose separation requires two independent keys — generate a new "
            "vault KEK before starting.",
        )
