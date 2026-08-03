"""ML-DSA-65 (FIPS 204) via ``pqcrypto`` or liboqs ``oqs`` (shared library)."""

from __future__ import annotations

from typing import Any

from ._util import validate_bytes, zero_memory
from .exceptions import KeyError_, SignatureError

__all__ = ["ML_DSA_AVAILABLE", "generate_keypair", "sign", "verify"]

ML_DSA_AVAILABLE = False
_BACKEND: str | None = None
_SIG_ALG: str = "ML-DSA-65"
_pq: Any = None
_oqs: Any = None

# FIPS 204 ML-DSA-65 (category 3) raw key/signature sizes (pqcrypto / typical OQS).
ML_DSA65_SECRET_KEY_BYTES = 4032
ML_DSA65_PUBLIC_KEY_BYTES = 1952
ML_DSA65_SIGNATURE_BYTES = 3309


def _try_pqcrypto() -> bool:
    global ML_DSA_AVAILABLE, _BACKEND, _pq
    try:
        from pqcrypto.sign import ml_dsa_65 as pq_mod

        _pq = pq_mod
        ML_DSA_AVAILABLE = True
        _BACKEND = "pqcrypto"
        return True
    except ImportError:
        return False


def _try_oqs() -> bool:
    global ML_DSA_AVAILABLE, _BACKEND, _SIG_ALG, _oqs
    try:
        import oqs
    except ImportError:
        return False

    _oqs = oqs
    for name in ("ML-DSA-65", "ML_DSA_65", "Dilithium3"):
        try:
            sig = oqs.Signature(name)
            sig.free()
            ML_DSA_AVAILABLE = True
            _BACKEND = "oqs"
            _SIG_ALG = name
            return True
        except (AttributeError, RuntimeError, ValueError):
            continue
    return False


_try_pqcrypto() or _try_oqs()


def generate_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_key_bytes, public_key_bytes)`` for ML-DSA-65."""
    if not ML_DSA_AVAILABLE:
        raise KeyError_(
            "ML-DSA-65 requires pqcrypto — install with: pip install pqcrypto",
        )
    try:
        if _BACKEND == "pqcrypto" and _pq is not None:
            public_key, secret_key = _pq.generate_keypair()
            return (secret_key, public_key)
        if _BACKEND == "oqs" and _oqs is not None:
            with _oqs.Signature(_SIG_ALG) as sig:
                public_key = sig.generate_keypair()
                private_key = sig.export_secret_key()
            return (private_key, public_key)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise KeyError_("ML-DSA-65 key generation failed") from exc
    raise KeyError_(
        "ML-DSA-65 requires pqcrypto — install with: pip install pqcrypto",
    )


def sign(message: bytes, private_key: bytes) -> bytes:
    """Sign ``message`` with a raw ML-DSA-65 private key."""
    validate_bytes(message, "message", min_len=1)
    validate_bytes(private_key, "private_key", exact_len=ML_DSA65_SECRET_KEY_BYTES)
    if not ML_DSA_AVAILABLE:
        raise KeyError_(
            "ML-DSA-65 requires pqcrypto — install with: pip install pqcrypto",
        )
    key_copy = bytearray(private_key)
    try:
        if _BACKEND == "pqcrypto" and _pq is not None:
            try:
                return bytes(_pq.sign(bytes(key_copy), message))
            except (ValueError, TypeError, RuntimeError) as exc:
                raise SignatureError("ML-DSA-65 signing failed") from exc
        if _BACKEND == "oqs" and _oqs is not None:
            try:
                with _oqs.Signature(_SIG_ALG) as sig:
                    sig.import_secret_key(bytes(key_copy))
                    return bytes(sig.sign(message))
            except (RuntimeError, ValueError, TypeError) as exc:
                raise SignatureError("ML-DSA-65 signing failed") from exc
    finally:
        zero_memory(key_copy)
    raise KeyError_(
        "ML-DSA-65 requires pqcrypto — install with: pip install pqcrypto",
    )


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify an ML-DSA-65 signature (returns False on invalid signature)."""
    validate_bytes(message, "message", min_len=1)
    validate_bytes(signature, "signature", exact_len=ML_DSA65_SIGNATURE_BYTES)
    validate_bytes(public_key, "public_key", exact_len=ML_DSA65_PUBLIC_KEY_BYTES)
    if not ML_DSA_AVAILABLE:
        return False
    if _BACKEND == "pqcrypto" and _pq is not None:
        try:
            return bool(_pq.verify(public_key, message, signature))
        except (ValueError, TypeError, RuntimeError):
            return False
    if _BACKEND == "oqs" and _oqs is not None:
        try:
            with _oqs.Signature(_SIG_ALG) as sig:
                sig.import_public_key(public_key)
                return bool(sig.verify(message, signature))
        except (RuntimeError, ValueError, TypeError):
            return False
    return False
