"""Unit tests for RFC 3161 TSA client."""

from __future__ import annotations

import hashlib

import pytest

from axiom.services.crypto import timestamp


@pytest.mark.asyncio
async def test_mock_tsa_returns_token() -> None:
    h = hashlib.sha256(b"x").digest()
    prov = timestamp.MockTSAProvider()
    tok = await prov.timestamp(h)
    assert tok is not None
    assert tok.hash_algorithm == "sha-256"
    assert tok.tsa_name == "mock-tsa"
    assert len(tok.token_bytes) > 0


@pytest.mark.asyncio
async def test_free_tsa_stub_without_asn1(monkeypatch) -> None:
    monkeypatch.setattr(timestamp, "TSA_AVAILABLE", False)
    prov = timestamp.FreeTSAProvider()
    with pytest.raises(NotImplementedError, match="asn1crypto"):
        await prov.timestamp(hashlib.sha256(b"y").digest())
