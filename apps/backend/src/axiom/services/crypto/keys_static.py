"""Static file-based key provider for development. NOT for production. ADR-026."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import ed25519, ml_dsa_65
from .exceptions import KeyError_
from .keys import KeyMetadata, KeyProvider, KeyStatus

logger = logging.getLogger(__name__)

_META_SUFFIX = ".meta.json"
_CURRENT_SUFFIX = ".current"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(s: str) -> datetime:
    raw = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class StaticKeyProvider(KeyProvider):
    """Development KeyProvider: raw keys on disk with JSON sidecar metadata per key."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = (base_dir or Path(".axiom") / "keys").resolve()
        logger.warning("Using static key provider — NOT for production")

    def _algorithm_paths(self, algorithm: str) -> tuple[Path, Path]:
        safe = algorithm.replace("/", "_")
        return self._base / f"{safe}{_CURRENT_SUFFIX}", self._base / safe

    def _read_current_id(self, algorithm: str) -> str | None:
        cur_file, _ = self._algorithm_paths(algorithm)
        if not cur_file.is_file():
            return None
        return cur_file.read_text(encoding="utf-8").strip() or None

    def _write_current_id(self, algorithm: str, key_id: str) -> None:
        cur_file, _ = self._algorithm_paths(algorithm)
        cur_file.parent.mkdir(parents=True, exist_ok=True)
        cur_file.write_text(key_id + "\n", encoding="utf-8")

    def _meta_path(self, key_id: str) -> Path:
        return self._base / f"{key_id}{_META_SUFFIX}"

    def _sk_path(self, key_id: str) -> Path:
        return self._base / f"{key_id}.sk"

    def _pk_path(self, key_id: str) -> Path:
        return self._base / f"{key_id}.pk"

    def _load_meta(self, key_id: str) -> dict[str, Any]:
        p = self._meta_path(key_id)
        if not p.is_file():
            msg = f"missing metadata for key_id={key_id}"
            raise KeyError_(msg)
        return json.loads(p.read_text(encoding="utf-8"))

    def _save_meta(self, meta: KeyMetadata) -> None:
        data = {
            "key_id": meta.key_id,
            "algorithm": meta.algorithm,
            "status": meta.status.value,
            "created_at": _iso(meta.created_at),
            "rotated_at": _iso(meta.rotated_at) if meta.rotated_at else None,
            "expires_at": _iso(meta.expires_at) if meta.expires_at else None,
            "successor_key_id": meta.successor_key_id,
        }
        p = self._meta_path(meta.key_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _meta_from_dict(self, d: dict[str, Any]) -> KeyMetadata:
        return KeyMetadata(
            key_id=str(d["key_id"]),
            algorithm=str(d["algorithm"]),
            status=KeyStatus(str(d["status"])),
            created_at=_parse_iso(str(d["created_at"])),
            rotated_at=_parse_iso(str(d["rotated_at"])) if d.get("rotated_at") else None,
            expires_at=_parse_iso(str(d["expires_at"])) if d.get("expires_at") else None,
            successor_key_id=str(d["successor_key_id"]) if d.get("successor_key_id") else None,
        )

    def _next_key_id(self, algorithm: str) -> str:
        _, prefix = self._algorithm_paths(algorithm)
        pat = f"{prefix.name}-*.meta.json"
        max_n = 0
        for p in self._base.glob(pat):
            stem = p.name[: -len(_META_SUFFIX)]
            parts = stem.split("-")
            if len(parts) >= 2 and parts[-1].isdigit():
                max_n = max(max_n, int(parts[-1]))
        return f"{prefix.name}-{max_n + 1:06d}"

    def _ensure_active_key(self, algorithm: str) -> KeyMetadata:
        self._base.mkdir(parents=True, exist_ok=True)
        current = self._read_current_id(algorithm)
        if current:
            meta = self._meta_from_dict(self._load_meta(current))
            if meta.status == KeyStatus.ACTIVE:
                return meta
        return self._generate_new_key(algorithm, reason="initial")

    def _generate_new_key(self, algorithm: str, *, reason: str) -> KeyMetadata:
        key_id = self._next_key_id(algorithm)
        now = _utcnow()
        if algorithm == "ed25519":
            sk, pk = ed25519.generate_keypair(raw=True)
        elif algorithm == "ml-dsa-65":
            if not ml_dsa_65.ML_DSA_AVAILABLE:
                msg = "ML-DSA-65 requires pqcrypto — install with: pip install pqcrypto"
                raise KeyError_(msg)
            sk, pk = ml_dsa_65.generate_keypair()
        else:
            msg = f"unsupported algorithm for static provider: {algorithm}"
            raise KeyError_(msg)

        self._sk_path(key_id).write_bytes(sk)
        self._pk_path(key_id).write_bytes(pk)
        meta = KeyMetadata(
            key_id=key_id,
            algorithm=algorithm,
            status=KeyStatus.ACTIVE,
            created_at=now,
            rotated_at=None,
            expires_at=None,
            successor_key_id=None,
        )
        self._save_meta(meta)
        self._write_current_id(algorithm, key_id)
        logger.info("static key generated: %s (%s)", key_id, reason)
        return meta

    async def get_signing_key(self, algorithm: str) -> tuple[bytes, KeyMetadata]:
        def _run() -> tuple[bytes, KeyMetadata]:
            meta = self._ensure_active_key(algorithm)
            if meta.status != KeyStatus.ACTIVE:
                msg = f"no active signing key for {algorithm}"
                raise KeyError_(msg)
            sk = self._sk_path(meta.key_id).read_bytes()
            return sk, meta

        return await asyncio.to_thread(_run)

    async def get_verification_key(self, key_id: str) -> tuple[bytes, KeyMetadata]:
        def _run() -> tuple[bytes, KeyMetadata]:
            meta = self._meta_from_dict(self._load_meta(key_id))
            if meta.status == KeyStatus.DESTROYED:
                msg = f"key {key_id} is destroyed"
                raise KeyError_(msg)
            pk = self._pk_path(key_id).read_bytes()
            return pk, meta

        return await asyncio.to_thread(_run)

    async def rotate_key(self, algorithm: str, reason: str) -> KeyMetadata:
        def _run() -> KeyMetadata:
            self._ensure_active_key(algorithm)
            old_id = self._read_current_id(algorithm)
            if not old_id:
                msg = f"cannot rotate: no current key for {algorithm}"
                raise KeyError_(msg)
            old_meta = self._meta_from_dict(self._load_meta(old_id))
            if old_meta.status != KeyStatus.ACTIVE:
                msg = f"cannot rotate: current key {old_id} is not ACTIVE"
                raise KeyError_(msg)
            now = _utcnow()
            new_meta_inner = self._generate_new_key(algorithm, reason=f"rotation: {reason}")
            rotated = KeyMetadata(
                key_id=old_meta.key_id,
                algorithm=old_meta.algorithm,
                status=KeyStatus.ROTATE_OUT,
                created_at=old_meta.created_at,
                rotated_at=now,
                expires_at=old_meta.expires_at,
                successor_key_id=new_meta_inner.key_id,
            )
            self._save_meta(rotated)
            return new_meta_inner

        return await asyncio.to_thread(_run)

    async def list_keys(self, algorithm: str | None = None) -> list[KeyMetadata]:
        def _run() -> list[KeyMetadata]:
            if not self._base.is_dir():
                return []
            out: list[KeyMetadata] = []
            for p in sorted(self._base.glob(f"*{_META_SUFFIX}")):
                try:
                    kid = p.name.removesuffix(_META_SUFFIX)
                    m = self._meta_from_dict(self._load_meta(kid))
                except (json.JSONDecodeError, KeyError, OSError, ValueError):
                    continue
                if algorithm is None or m.algorithm == algorithm:
                    out.append(m)
            return sorted(out, key=lambda x: x.key_id)

        return await asyncio.to_thread(_run)
