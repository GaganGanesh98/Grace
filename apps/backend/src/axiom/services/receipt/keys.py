"""Singleton loader for the Phase 2 AXIOM-wide signing + evidence keys.

Policy:
  * In ``environment`` in {"development", "test"}: if any of the five env vars
    is missing, auto-generate fresh values, **persist them to
    ``apps/backend/.env``** so every process (backend, gateway, worker) shares
    the same material, and emit a LOUD warning log so ops see it.
  * In ``environment == "production"``: any missing value raises
    ``MissingSigningKeysError`` at load time, refusing startup. No silent
    defaults in production.

Per-project keys land in Phase 2.5. Until then, the whole API shares one
Ed25519 keypair, one ML-DSA-65 keypair, and one AES-256-GCM evidence key.
"""

from __future__ import annotations

import base64
import hashlib
import os
import threading
from dataclasses import dataclass

import structlog
from pydantic import SecretBytes, SecretStr

from axiom.config import REPO_ROOT, get_settings
from axiom.services.crypto import aes_gcm, ed25519, ml_dsa

logger = structlog.get_logger(__name__)


class MissingSigningKeysError(RuntimeError):
    """Raised in production when any Phase-2 key env var is absent."""


@dataclass(frozen=True)
class SigningKeys:
    ed25519_private: SecretStr
    ed25519_public: str
    ed25519_key_id: str
    ml_dsa_private: SecretBytes
    ml_dsa_public: bytes
    ml_dsa_key_id: str
    evidence_key: bytes
    evidence_key_id: str


_cache: SigningKeys | None = None
_lock = threading.Lock()


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _is_dev_or_test(environment: str) -> bool:
    return environment.lower() in {"development", "test", "testing", "local"}


def _missing_fields(settings: object) -> list[str]:
    missing: list[str] = []
    pairs: tuple[tuple[str, object], ...] = (
        ("AXIOM_ED25519_PRIVATE_PEM", getattr(settings, "axiom_ed25519_private_pem", None)),
        ("AXIOM_ED25519_PUBLIC_PEM", getattr(settings, "axiom_ed25519_public_pem", None)),
        ("AXIOM_ML_DSA_PRIVATE_B64", getattr(settings, "axiom_ml_dsa_private_b64", None)),
        ("AXIOM_ML_DSA_PUBLIC_B64", getattr(settings, "axiom_ml_dsa_public_b64", None)),
        ("AXIOM_EVIDENCE_KEY_B64", getattr(settings, "axiom_evidence_key_b64", None)),
    )
    for name, value in pairs:
        if value is None or value == "":
            missing.append(name)
    return missing


def _dotenv_escape(value: str) -> str:
    """Wrap in double quotes if the value contains newlines (e.g. PEM blocks)."""
    if "\n" in value:
        return f'"{value}"'
    return value


def _persist_to_dotenv(env_vars: dict[str, str]) -> None:
    """Append auto-generated key env vars to apps/backend/.env so every process shares them."""
    dotenv_path = REPO_ROOT / "apps" / "backend" / ".env"
    try:
        existing = dotenv_path.read_text() if dotenv_path.exists() else ""
        lines_to_add: list[str] = []
        for key, value in env_vars.items():
            if f"{key}=" not in existing:
                lines_to_add.append(f"{key}={_dotenv_escape(value)}")
        if lines_to_add:
            separator = "\n" if existing and not existing.endswith("\n") else ""
            with open(dotenv_path, "a") as f:
                f.write(separator + "\n".join(lines_to_add) + "\n")
            logger.info("axiom.keys.persisted_to_dotenv", path=str(dotenv_path), keys=list(env_vars.keys()))
    except OSError:
        logger.warning("axiom.keys.persist_failed", path=str(dotenv_path), exc_info=True)


def _autogenerate() -> SigningKeys:
    ed = ed25519.generate_keypair()
    ml = ml_dsa.generate_keypair()
    ev = aes_gcm.generate_key()
    keys = SigningKeys(
        ed25519_private=ed.private_key_pem,
        ed25519_public=ed.public_key_pem,
        ed25519_key_id=ed.key_id,
        ml_dsa_private=ml.private_key_bytes,
        ml_dsa_public=ml.public_key_bytes,
        ml_dsa_key_id=ml.key_id,
        evidence_key=ev,
        evidence_key_id=hashlib.sha256(ev).hexdigest(),
    )
    _persist_to_dotenv(export_b64(keys))
    return keys


def _from_settings() -> SigningKeys:
    s = get_settings()
    priv_pem = s.axiom_ed25519_private_pem
    pub_pem = s.axiom_ed25519_public_pem
    ml_priv_b64 = s.axiom_ml_dsa_private_b64
    ml_pub_b64 = s.axiom_ml_dsa_public_b64
    ev_b64 = s.axiom_evidence_key_b64

    assert priv_pem is not None
    assert pub_pem is not None
    assert ml_priv_b64 is not None
    assert ml_pub_b64 is not None
    assert ev_b64 is not None

    ml_priv_bytes = _b64decode(ml_priv_b64.get_secret_value())
    ml_pub_bytes = _b64decode(ml_pub_b64)
    ev = _b64decode(ev_b64.get_secret_value())
    if len(ev) != 32:
        msg = "AXIOM_EVIDENCE_KEY_B64 must decode to 32 bytes (AES-256-GCM)"
        raise ValueError(msg)

    return SigningKeys(
        ed25519_private=priv_pem,
        ed25519_public=pub_pem,
        ed25519_key_id=ed25519.stable_key_id(pub_pem),
        ml_dsa_private=SecretBytes(ml_priv_bytes),
        ml_dsa_public=ml_pub_bytes,
        ml_dsa_key_id=ml_dsa.stable_key_id(ml_pub_bytes),
        evidence_key=ev,
        evidence_key_id=hashlib.sha256(ev).hexdigest(),
    )


def get_signing_keys() -> SigningKeys:
    """Return the process-wide Phase-2 keys. Cached after first call."""

    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        settings = get_settings()
        missing = _missing_fields(settings)
        if missing:
            if _is_dev_or_test(settings.environment):
                logger.warning(
                    "axiom.keys.autogenerated",
                    environment=settings.environment,
                    missing=missing,
                    note=(
                        "Phase 2 governance keys were missing. "
                        "Auto-generated and persisted to apps/backend/.env "
                        "so all processes (backend, gateway, worker) share them."
                    ),
                )
                _cache = _autogenerate()
                return _cache
            msg = (
                "Missing required Phase-2 signing/evidence keys in production: "
                + ", ".join(missing)
                + ". Refusing to start. Set all five env vars before deploy."
            )
            raise MissingSigningKeysError(msg)
        _cache = _from_settings()
        return _cache


def preflight_ensure_keys() -> dict[str, str]:
    """Generate+persist Phase-2 keys IFF any are missing.

    Returns {key_id_name: key_id_hex} for logging. Never returns secret
    material. Idempotent. Raises MissingSigningKeysError in production.
    Raises OSError if .env is unwritable.
    """
    settings = get_settings()
    missing = _missing_fields(settings)
    if not missing:
        keys = _from_settings()
        logger.info("axiom.keys.preflight_noop", note="all keys already present")
        return {
            "ed25519_key_id": keys.ed25519_key_id,
            "ml_dsa_key_id": keys.ml_dsa_key_id,
            "evidence_key_id": keys.evidence_key_id,
        }
    if not _is_dev_or_test(settings.environment):
        msg = (
            "Missing required Phase-2 signing/evidence keys in production: "
            + ", ".join(missing)
            + ". Refusing to start. Set all five env vars before deploy."
        )
        raise MissingSigningKeysError(msg)
    dotenv_path = REPO_ROOT / "apps" / "backend" / ".env"
    if dotenv_path.exists() and not os.access(dotenv_path, os.W_OK):
        msg = f"Cannot write to {dotenv_path} — fix permissions or pre-populate keys."
        raise OSError(msg)
    keys = _autogenerate()
    logger.warning(
        "axiom.keys.preflight_generated",
        environment=settings.environment,
        missing=missing,
    )
    return {
        "ed25519_key_id": keys.ed25519_key_id,
        "ml_dsa_key_id": keys.ml_dsa_key_id,
        "evidence_key_id": keys.evidence_key_id,
    }


def reset_for_tests() -> None:
    """Test hook: drop the cached keys so the next call re-reads settings."""
    global _cache
    with _lock:
        _cache = None


def export_b64(keys: SigningKeys) -> dict[str, str]:
    """Helper for ops: dump the key material in base64 so they can pin it
    in env. Never call this from app code."""
    return {
        "AXIOM_ED25519_PRIVATE_PEM": keys.ed25519_private.get_secret_value(),
        "AXIOM_ED25519_PUBLIC_PEM": keys.ed25519_public,
        "AXIOM_ML_DSA_PRIVATE_B64": _b64encode(keys.ml_dsa_private.get_secret_value()),
        "AXIOM_ML_DSA_PUBLIC_B64": _b64encode(keys.ml_dsa_public),
        "AXIOM_EVIDENCE_KEY_B64": _b64encode(keys.evidence_key),
    }
