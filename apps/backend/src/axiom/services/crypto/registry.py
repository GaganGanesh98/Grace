"""Algorithm registry for crypto agility (ADR-024)."""

from __future__ import annotations

import hashlib
import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from . import ed25519, ml_dsa_65, vault
from .exceptions import AlgorithmNotFoundError, CryptoError, CryptoInputError

__all__ = [
    "AlgorithmRegistry",
    "AlgorithmStatus",
    "Decryptor",
    "Encryptor",
    "Hasher",
    "RegisteredAlgorithm",
    "Signer",
    "Verifier",
]

Signer = Callable[[bytes, bytes], bytes]
Verifier = Callable[[bytes, bytes, bytes], bool]
Encryptor = Callable[[bytes, bytes], bytes]
Decryptor = Callable[[bytes, bytes], bytes]
Hasher = Callable[[bytes], bytes]


class AlgorithmStatus(Enum):
    ACTIVE = "active"  # Can sign and verify
    DEPRECATED = "deprecated"  # Can verify only, signing raises DeprecationWarning + logs
    REVOKED = "revoked"  # Cannot sign, verify raises CryptoError


@dataclass
class RegisteredAlgorithm:
    name: str
    status: AlgorithmStatus
    signer: Signer | None
    verifier: Verifier | None
    deprecated_since: datetime | None = None
    revoked_since: datetime | None = None
    reason: str | None = None  # Why deprecated/revoked
    successor: str | None = None  # What algorithm to use instead


def _ed25519_sign(message: bytes, private_key: bytes) -> bytes:
    return ed25519.sign(message, private_key)


def _ed25519_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    return ed25519.verify(message, signature, public_key)


def _ml_dsa_sign(message: bytes, private_key: bytes) -> bytes:
    return ml_dsa_65.sign(message, private_key)


def _ml_dsa_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    return ml_dsa_65.verify(message, signature, public_key)


def _validate_algo_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise CryptoInputError("algorithm name must be a non-empty string")
    return name


class AlgorithmRegistry:
    """Maps algorithm identifiers to signing, verification, hashing, and AEAD helpers."""

    __slots__ = ("_encryptors", "_hashers", "_registered")

    def __init__(self) -> None:
        self._registered: dict[str, RegisteredAlgorithm] = {
            "ed25519": RegisteredAlgorithm(
                name="ed25519",
                status=AlgorithmStatus.ACTIVE,
                signer=_ed25519_sign,
                verifier=_ed25519_verify,
                deprecated_since=None,
                revoked_since=None,
                reason=None,
                successor=None,
            ),
            "ml-dsa-65": RegisteredAlgorithm(
                name="ml-dsa-65",
                status=AlgorithmStatus.ACTIVE,
                signer=_ml_dsa_sign,
                verifier=_ml_dsa_verify,
                deprecated_since=None,
                revoked_since=None,
                reason=None,
                successor=None,
            ),
        }
        self._encryptors: dict[str, Encryptor] = {
            "aes-256-gcm": vault.encrypt,
        }
        self._hashers: dict[str, Hasher] = {
            "sha-256": lambda b: hashlib.sha256(b).digest(),
        }

    def deprecate_algorithm(
        self,
        name: str,
        reason: str,
        successor: str,
        *,
        since: datetime | None = None,
    ) -> None:
        """Mark a signing algorithm as deprecated (verify still allowed)."""
        name = _validate_algo_name(name)
        if name not in self._registered:
            raise AlgorithmNotFoundError(f"unknown signing algorithm: {name}")
        when = since or datetime.now(UTC)
        cur = self._registered[name]
        self._registered[name] = RegisteredAlgorithm(
            name=cur.name,
            status=AlgorithmStatus.DEPRECATED,
            signer=cur.signer,
            verifier=cur.verifier,
            deprecated_since=when,
            revoked_since=cur.revoked_since,
            reason=reason,
            successor=successor,
        )

    def revoke_algorithm(self, name: str, reason: str, *, since: datetime | None = None) -> None:
        """Revoke a signing algorithm (no signing; verification blocked)."""
        name = _validate_algo_name(name)
        if name not in self._registered:
            raise AlgorithmNotFoundError(f"unknown signing algorithm: {name}")
        when = since or datetime.now(UTC)
        cur = self._registered[name]
        self._registered[name] = RegisteredAlgorithm(
            name=cur.name,
            status=AlgorithmStatus.REVOKED,
            signer=cur.signer,
            verifier=cur.verifier,
            deprecated_since=cur.deprecated_since,
            revoked_since=when,
            reason=reason,
            successor=cur.successor,
        )

    def get_signer(self, name: str) -> Signer:
        name = _validate_algo_name(name)
        if name not in self._registered:
            raise AlgorithmNotFoundError(f"unknown signing algorithm: {name}")
        reg = self._registered[name]
        if reg.status == AlgorithmStatus.REVOKED:
            rs = reg.revoked_since.isoformat() if reg.revoked_since else "unknown date"
            succ = reg.successor or "a supported algorithm"
            raise AlgorithmNotFoundError(f"{name} is revoked since {rs}: {reg.reason}. Use {succ}.")
        if reg.status == AlgorithmStatus.DEPRECATED:
            logging.getLogger(__name__).warning(
                "signing with deprecated algorithm: %s (%s) — use %s",
                name,
                reg.reason,
                reg.successor,
            )
            warnings.warn(
                f"{name} is deprecated: {reg.reason}. Prefer {reg.successor}.",
                DeprecationWarning,
                stacklevel=2,
            )
        if reg.signer is None:
            raise AlgorithmNotFoundError(f"no signer for algorithm: {name}")
        return reg.signer

    def get_verifier(self, name: str) -> Verifier:
        name = _validate_algo_name(name)
        if name not in self._registered:
            raise AlgorithmNotFoundError(f"unknown verification algorithm: {name}")
        reg = self._registered[name]
        if reg.status == AlgorithmStatus.REVOKED:
            rs = reg.revoked_since.isoformat() if reg.revoked_since else "unknown date"
            succ = reg.successor or "a supported algorithm"
            msg = (
                f"{name} is revoked since {rs}: {reg.reason}. "
                f"Verification not allowed. Use {succ}."
            )
            raise CryptoError(msg)
        if reg.verifier is None:
            raise AlgorithmNotFoundError(f"no verifier for algorithm: {name}")
        return reg.verifier

    def get_encryptor(self, name: str) -> Encryptor:
        name = _validate_algo_name(name)
        if name not in self._encryptors:
            raise AlgorithmNotFoundError(f"unknown encryptor: {name}")
        return self._encryptors[name]

    def get_hasher(self, name: str) -> Hasher:
        name = _validate_algo_name(name)
        if name not in self._hashers:
            raise AlgorithmNotFoundError(f"unknown hasher: {name}")
        return self._hashers[name]
