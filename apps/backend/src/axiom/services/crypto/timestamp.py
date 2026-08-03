"""RFC 3161 Trusted Timestamp Authority client.

Proves a receipt existed at a specific time, independently of AXIOM.
Court-admissibility requires timestamps from a trusted third party, not just our own clock.
"""

from __future__ import annotations

import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx

from .audit import log_tsa_attempt

try:
    from asn1crypto import tsp  # noqa: F401

    TSA_AVAILABLE = True
except ImportError:
    TSA_AVAILABLE = False


@dataclass(frozen=True)
class TimestampToken:
    tsa_name: str
    timestamp_utc: datetime
    token_bytes: bytes
    hash_algorithm: str


class TimestampAuthority(ABC):
    """Abstract trusted timestamp authority (RFC 3161)."""

    @abstractmethod
    async def timestamp(self, data_hash: bytes) -> TimestampToken | None:
        """Request a timestamp for a SHA-256 message imprint (32 bytes)."""


def _build_timestamp_request(data_hash: bytes) -> bytes:
    from asn1crypto import core
    from asn1crypto import tsp as tsp_mod
    from asn1crypto.algos import DigestAlgorithm

    if len(data_hash) != 32:
        msg = "data_hash must be SHA-256 (32 bytes)"
        raise ValueError(msg)
    mi = tsp_mod.MessageImprint(
        {
            "hash_algorithm": DigestAlgorithm({"algorithm": "sha256"}),
            "hashed_message": data_hash,
        },
    )
    req = tsp_mod.TimeStampReq(
        {
            "version": 1,
            "message_imprint": mi,
            "cert_req": core.Boolean(value=True),
            "nonce": int.from_bytes(secrets.token_bytes(8), "big"),
        },
    )
    return cast(bytes, req.dump())


def _parse_timestamp_response(body: bytes) -> tuple[datetime, str]:
    from asn1crypto import tsp as tsp_mod

    resp = tsp_mod.TimeStampResp.load(body)
    native = resp.native
    if not isinstance(native, dict):
        msg = "unexpected TimeStampResp shape"
        raise ValueError(msg)
    status_info = native.get("status") or {}
    status_str = status_info.get("status")
    if status_str != "granted":
        msg = f"TSA status not granted: {status_str}"
        raise ValueError(msg)
    tst_wrapped = native.get("time_stamp_token")
    if not isinstance(tst_wrapped, dict):
        msg = "missing time_stamp_token"
        raise ValueError(msg)
    content = tst_wrapped.get("content")
    if not isinstance(content, dict):
        msg = "missing SignedData"
        raise ValueError(msg)
    encap = content.get("encap_content_info") or {}
    tst_native = encap.get("content")
    if not isinstance(tst_native, dict):
        msg = "missing TSTInfo"
        raise ValueError(msg)
    gen_time = tst_native.get("gen_time")
    if not isinstance(gen_time, datetime):
        msg = "missing gen_time"
        raise ValueError(msg)
    gen_time = gen_time.replace(tzinfo=UTC) if gen_time.tzinfo is None else gen_time.astimezone(UTC)
    tsa = tst_native.get("tsa")
    tsa_name = "unknown"
    if isinstance(tsa, dict) and tsa.get("common_name"):
        tsa_name = str(tsa["common_name"])
    elif isinstance(tsa, str):
        tsa_name = tsa
    return gen_time, tsa_name


class FreeTSAProvider(TimestampAuthority):
    """Public FreeTSA.org RFC 3161 endpoint (development / demonstration)."""

    _URL = "https://freetsa.org/tsr"

    async def timestamp(self, data_hash: bytes) -> TimestampToken | None:
        if not TSA_AVAILABLE:
            raise NotImplementedError(
                "RFC 3161 TSA requires asn1crypto — install with: pip install asn1crypto",
            )
        t0 = time.perf_counter()
        status: str | None = "not_attempted"
        try:
            der = _build_timestamp_request(data_hash)
        except (OSError, TypeError, ValueError) as exc:
            log_tsa_attempt(
                "FreeTSA",
                success=False,
                status=str(exc),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    self._URL,
                    content=der,
                    headers={"Content-Type": "application/timestamp-query"},
                )
            r.raise_for_status()
            ts_utc, tsa_name = _parse_timestamp_response(r.content)
            status = "granted"
            dur = (time.perf_counter() - t0) * 1000
            log_tsa_attempt(
                "FreeTSA",
                success=True,
                status=status,
                duration_ms=dur,
            )
            return TimestampToken(
                tsa_name=tsa_name,
                timestamp_utc=ts_utc,
                token_bytes=bytes(r.content),
                hash_algorithm="sha-256",
            )
        except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
            status = type(exc).__name__
            log_tsa_attempt(
                "FreeTSA",
                success=False,
                status=status,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            return None


class MockTSAProvider(TimestampAuthority):
    """Deterministic offline TSA for unit tests."""

    async def timestamp(self, data_hash: bytes) -> TimestampToken | None:
        if len(data_hash) != 32:
            return None
        now = datetime.now(UTC)
        tok = b"MOCK-TST-" + data_hash[:8]
        return TimestampToken(
            tsa_name="mock-tsa",
            timestamp_utc=now,
            token_bytes=tok,
            hash_algorithm="sha-256",
        )
