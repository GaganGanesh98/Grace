"""Algorithm lifecycle on AlgorithmRegistry."""

from __future__ import annotations

import warnings

import pytest

from axiom.services.crypto.exceptions import AlgorithmNotFoundError, CryptoError
from axiom.services.crypto.registry import AlgorithmRegistry


def test_deprecate_warns_on_sign_still_verifies() -> None:
    r = AlgorithmRegistry()
    r.deprecate_algorithm("ed25519", reason="test", successor="ml-dsa-65")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r.get_signer("ed25519")
        assert any(issubclass(x.category, DeprecationWarning) for x in w)
    v = r.get_verifier("ed25519")
    assert callable(v)


def test_revoke_blocks_sign_and_verify() -> None:
    r = AlgorithmRegistry()
    r.revoke_algorithm("ed25519", reason="compromise")
    with pytest.raises(AlgorithmNotFoundError, match="revoked"):
        r.get_signer("ed25519")
    with pytest.raises(CryptoError, match="revoked"):
        r.get_verifier("ed25519")
