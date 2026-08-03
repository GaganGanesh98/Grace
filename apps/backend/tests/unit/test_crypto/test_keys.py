"""Unit tests for key management abstraction (static dev provider)."""

from __future__ import annotations

import pytest

from axiom.services.crypto.keys import KeyStatus
from axiom.services.crypto.keys_static import StaticKeyProvider


@pytest.mark.asyncio
async def test_static_ed25519_generate_and_sign_path(tmp_path) -> None:
    p = StaticKeyProvider(base_dir=tmp_path / "k")
    sk, meta = await p.get_signing_key("ed25519")
    assert len(sk) == 32
    assert meta.status == KeyStatus.ACTIVE
    assert meta.algorithm == "ed25519"
    pk, vmeta = await p.get_verification_key(meta.key_id)
    assert len(pk) == 32
    assert vmeta.key_id == meta.key_id


@pytest.mark.asyncio
async def test_static_rotate_advances_successor(tmp_path) -> None:
    p = StaticKeyProvider(base_dir=tmp_path / "k")
    _, m0 = await p.get_signing_key("ed25519")
    m1 = await p.rotate_key("ed25519", reason="test-rotation")
    assert m1.key_id != m0.key_id
    assert m1.status == KeyStatus.ACTIVE
    old = next(x for x in await p.list_keys("ed25519") if x.key_id == m0.key_id)
    assert old.status == KeyStatus.ROTATE_OUT
    assert old.successor_key_id == m1.key_id


@pytest.mark.asyncio
async def test_kms_stub_raises() -> None:
    from axiom.services.crypto.keys_kms import KMSKeyProvider

    kms = KMSKeyProvider()
    with pytest.raises(NotImplementedError, match="ADR-026"):
        await kms.get_signing_key("ed25519")
