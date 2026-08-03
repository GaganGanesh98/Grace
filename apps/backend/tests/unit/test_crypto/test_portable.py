"""Unit tests for portable verification bundles."""

from __future__ import annotations

import json

from axiom.services.crypto.portable import VerificationBundle, create_bundle


def test_bundle_json_round_trip() -> None:
    b = create_bundle(
        '{"r":1}',
        b"p" * 32,
        b"s" * 64,
        None,
        None,
        [b"h" * 32],
        b"r" * 32,
    )
    d = json.loads(b.to_json())
    assert d["hash_algorithm"] == "sha-256"
    assert "ed25519" in d["signature_algorithms"]
    assert d["ml_dsa_public_key"] is None
    assert len(d["merkle_proof"]) == 1
    assert len(VerificationBundle.verification_steps()) > 50
