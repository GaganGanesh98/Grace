"""Hybrid signatures: Ed25519 + ML-DSA-65 (ADR-022)."""

from __future__ import annotations

import hashlib
import logging
import time
from contextlib import suppress
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import ed25519, ml_dsa_65
from .audit import log_sign, log_verify
from ._util import validate_bytes

__all__ = ["HybridSignature", "hybrid_sign", "hybrid_verify"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HybridSignature:
    ed25519_sig: bytes
    ml_dsa_sig: bytes


def hybrid_sign(message: bytes, ed25519_private: bytes, ml_dsa_private: bytes) -> HybridSignature:
    t0 = time.perf_counter()
    success = False
    validate_bytes(message, "message", min_len=1)
    validate_bytes(ed25519_private, "ed25519_private", exact_len=32)
    if ml_dsa_65.ML_DSA_AVAILABLE:
        validate_bytes(
            ml_dsa_private,
            "ml_dsa_private",
            exact_len=ml_dsa_65.ML_DSA65_SECRET_KEY_BYTES,
        )
    epk = Ed25519PrivateKey.from_private_bytes(ed25519_private)
    kid = hashlib.sha256(
        epk.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    ).hexdigest()[:16]
    try:
        ed_sig = ed25519.sign(message, ed25519_private)
        if ml_dsa_65.ML_DSA_AVAILABLE:
            ml_sig = ml_dsa_65.sign(message, ml_dsa_private)
        else:
            logger.warning("ML-DSA-65 unavailable; hybrid uses empty ml_dsa_sig (stub mode)")
            ml_sig = b""
        success = True
        return HybridSignature(ed25519_sig=ed_sig, ml_dsa_sig=ml_sig)
    finally:
        mh = hashlib.sha256(message).hexdigest()
        with suppress(Exception):
            log_sign(
                "hybrid",
                kid,
                mh,
                success=success,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )


def hybrid_verify(
    message: bytes,
    sig: HybridSignature,
    ed25519_public: bytes,
    ml_dsa_public: bytes,
) -> bool:
    t0 = time.perf_counter()
    ok = False
    kid = hashlib.sha256(ed25519_public).hexdigest()[:16]
    validate_bytes(message, "message", min_len=1)
    validate_bytes(ed25519_public, "ed25519_public", exact_len=32)
    validate_bytes(sig.ed25519_sig, "ed25519_sig", exact_len=64)
    try:
        if not ed25519.verify(message, sig.ed25519_sig, ed25519_public):
            return False
        if ml_dsa_65.ML_DSA_AVAILABLE:
            if len(sig.ml_dsa_sig) != ml_dsa_65.ML_DSA65_SIGNATURE_BYTES:
                return False
            validate_bytes(
                ml_dsa_public,
                "ml_dsa_public",
                exact_len=ml_dsa_65.ML_DSA65_PUBLIC_KEY_BYTES,
            )
            ok = ml_dsa_65.verify(message, sig.ml_dsa_sig, ml_dsa_public)
            return ok
        if sig.ml_dsa_sig:
            logger.warning("ML-DSA stub mode but ml_dsa_sig is non-empty")
            return False
        logger.warning("Skipping ML-DSA verification (ML-DSA-65 not available)")
        ok = True
        return True
    finally:
        with suppress(Exception):
            log_verify(
                "hybrid",
                kid,
                success=ok,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
