"""Ed25519 signing using the ``cryptography`` library (PEM legacy + RFC 8032 raw bytes)."""

from __future__ import annotations

import hashlib
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, overload

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import SecretStr

from .audit import log_sign, log_verify
from ._util import validate_bytes, zero_memory
from .exceptions import CryptoInputError, SignatureError

__all__ = ["Ed25519KeyPair", "generate_keypair", "sign", "stable_key_id", "verify"]


@dataclass(frozen=True)
class Ed25519KeyPair:
    private_key_pem: SecretStr
    public_key_pem: str
    key_id: str


def _generate_pem_keypair() -> Ed25519KeyPair:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return Ed25519KeyPair(
        private_key_pem=SecretStr(priv_pem),
        public_key_pem=pub_pem,
        key_id=stable_key_id(pub_pem),
    )


@overload
def generate_keypair() -> Ed25519KeyPair: ...


@overload
def generate_keypair(*, raw: Literal[True]) -> tuple[bytes, bytes]: ...


def generate_keypair(*, raw: bool = False) -> Ed25519KeyPair | tuple[bytes, bytes]:
    """Return a PEM keypair (default) or RFC 8032 raw 32-byte keys (``raw=True``)."""
    if raw:
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        priv = sk.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub = pk.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return (priv, pub)
    return _generate_pem_keypair()


def _sign_pem(private_key_pem: SecretStr, message: bytes) -> bytes:
    pem_copy = bytearray(private_key_pem.get_secret_value().encode("utf-8"))
    try:
        try:
            private_key = serialization.load_pem_private_key(bytes(pem_copy), password=None)
        except (ValueError, TypeError) as exc:
            raise CryptoInputError("Invalid Ed25519 PEM private key") from exc
        if not isinstance(private_key, Ed25519PrivateKey):
            raise CryptoInputError("PEM must encode an Ed25519 private key")
        return private_key.sign(message)
    except CryptoInputError:
        raise
    except Exception as exc:  # noqa
        raise SignatureError("Ed25519 signing failed") from exc
    finally:
        zero_memory(pem_copy)


def _sign_raw(message: bytes, private_key: bytes) -> bytes:
    key_copy = bytearray(private_key)
    try:
        try:
            sk = Ed25519PrivateKey.from_private_bytes(bytes(key_copy))
        except (ValueError, TypeError) as exc:
            raise CryptoInputError("Invalid Ed25519 raw private key") from exc
        return sk.sign(message)
    except CryptoInputError:
        raise
    except Exception as exc:  # noqa
        raise SignatureError("Ed25519 signing failed") from exc
    finally:
        zero_memory(key_copy)


def _audit_key_id_from_raw_private(private_key: bytes) -> str:
    key_copy = bytearray(private_key)
    try:
        sk = Ed25519PrivateKey.from_private_bytes(bytes(key_copy))
        pub = sk.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(pub).hexdigest()[:16]
    except (ValueError, TypeError):
        return "unknown"
    finally:
        zero_memory(key_copy)


def _audit_key_id_from_pem_secret(private_key_pem: SecretStr) -> str:
    pem_copy = bytearray(private_key_pem.get_secret_value().encode("utf-8"))
    try:
        private_key = serialization.load_pem_private_key(bytes(pem_copy), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            return "unknown"
        pub_pem = (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        return stable_key_id(pub_pem)[:16]
    except (ValueError, TypeError, CryptoInputError):
        return "unknown"
    finally:
        zero_memory(pem_copy)


def sign(first: SecretStr | bytes, second: bytes) -> bytes:
    """Sign with PEM ``SecretStr`` (legacy) or RFC 8032 ``(message, private_key)``."""
    t0 = time.perf_counter()
    success = False
    key_id = "unknown"
    msg_for_hash: bytes = b""
    try:
        if isinstance(first, SecretStr):
            validate_bytes(second, "message", min_len=1)
            msg_for_hash = second
            key_id = _audit_key_id_from_pem_secret(first)
            out = _sign_pem(first, second)
            success = True
            return out
        if isinstance(first, bytes) and isinstance(second, bytes):
            validate_bytes(first, "message", min_len=1)
            validate_bytes(second, "private_key", exact_len=32)
            msg_for_hash = first
            key_id = _audit_key_id_from_raw_private(second)
            out = _sign_raw(first, second)
            success = True
            return out
        raise CryptoInputError(
            "sign: expected (SecretStr, bytes) or (message: bytes, private_key: bytes)",
        )
    finally:
        if msg_for_hash:
            mh = hashlib.sha256(msg_for_hash).hexdigest()
            with suppress(Exception):
                log_sign(
                    "ed25519",
                    key_id,
                    mh,
                    success=success,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )


def _verify_pem(public_key_pem: str, message: bytes, signature: bytes) -> bool:
    validate_bytes(message, "message", min_len=1)
    validate_bytes(signature, "signature", exact_len=64)
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        return False
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    if not isinstance(public_key, Ed25519PublicKey):
        return False
    try:
        public_key.verify(signature, message)
    except InvalidSignature:
        return False
    except (ValueError, TypeError):
        return False
    return True


def _verify_raw(message: bytes, signature: bytes, public_key: bytes) -> bool:
    validate_bytes(message, "message", min_len=1)
    validate_bytes(signature, "signature", exact_len=64)
    validate_bytes(public_key, "public_key", exact_len=32)
    try:
        pk = Ed25519PublicKey.from_public_bytes(public_key)
        pk.verify(signature, message)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def verify(first: str | bytes, second: bytes, third: bytes) -> bool:
    """Verify PEM public key (legacy) or RFC 8032 ``(message, signature, public_key)``."""
    t0 = time.perf_counter()
    key_id: str | None = None
    ok = False
    try:
        if isinstance(first, str):
            try:
                key_id = stable_key_id(first)[:16]
            except CryptoInputError:
                key_id = "unknown"
            ok = _verify_pem(first, second, third)
            return ok
        if isinstance(first, bytes):
            validate_bytes(third, "public_key", exact_len=32)
            key_id = hashlib.sha256(third).hexdigest()[:16]
            ok = _verify_raw(first, second, third)
            return ok
        raise CryptoInputError("verify: first argument must be str (PEM) or bytes (raw)")
    finally:
        with suppress(Exception):
            log_verify(
                "ed25519",
                key_id,
                success=ok,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )


def stable_key_id(public_key_pem: str) -> str:
    """SHA-256 of the DER-encoded public key, lowercase hex."""
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        raise CryptoInputError("public_key_pem must be a non-empty string")
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise CryptoInputError("Invalid PEM public key") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise CryptoInputError("PEM must encode an Ed25519 public key")
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()
