"""Key management abstraction — swap backends without changing callers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class KeyStatus(Enum):
    ACTIVE = "active"  # Can sign and verify
    ROTATE_OUT = "rotate_out"  # Can verify, new signatures use successor
    REVOKED = "revoked"  # Cannot sign, verify raises warning
    DESTROYED = "destroyed"  # Key material deleted, verify impossible


@dataclass(frozen=True)
class KeyMetadata:
    key_id: str  # Unique identifier, e.g. "axiom-ed25519-prod-2026-04"
    algorithm: str  # "ed25519" | "ml-dsa-65"
    status: KeyStatus
    created_at: datetime
    rotated_at: datetime | None  # When status changed from ACTIVE
    expires_at: datetime | None  # Hard expiry, None = no expiry
    successor_key_id: str | None  # What key replaced this one


class KeyProvider(ABC):
    """Abstract interface for key storage backends."""

    @abstractmethod
    async def get_signing_key(self, algorithm: str) -> tuple[bytes, KeyMetadata]:
        """Return the current ACTIVE private key + metadata for this algorithm."""

    @abstractmethod
    async def get_verification_key(self, key_id: str) -> tuple[bytes, KeyMetadata]:
        """Return public key + metadata for ``key_id`` (any status except DESTROYED)."""

    @abstractmethod
    async def rotate_key(self, algorithm: str, reason: str) -> KeyMetadata:
        """Generate a new key, mark old one as ROTATE_OUT, return new metadata."""

    @abstractmethod
    async def list_keys(self, algorithm: str | None = None) -> list[KeyMetadata]:
        """List all keys, optionally filtered by algorithm."""
