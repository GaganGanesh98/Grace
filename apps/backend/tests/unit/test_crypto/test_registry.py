"""Unit tests for AlgorithmRegistry."""

from __future__ import annotations

import hashlib

import pytest

from axiom.services.crypto.exceptions import AlgorithmNotFoundError
from axiom.services.crypto.registry import AlgorithmRegistry


def test_algorithms_registered() -> None:
    r = AlgorithmRegistry()
    h = r.get_hasher("sha-256")
    assert h(b"abc") == hashlib.sha256(b"abc").digest()
    r.get_signer("ed25519")
    r.get_verifier("ed25519")
    r.get_signer("ml-dsa-65")
    r.get_verifier("ml-dsa-65")
    r.get_encryptor("aes-256-gcm")


def test_unknown_algorithm_raises() -> None:
    r = AlgorithmRegistry()
    with pytest.raises(AlgorithmNotFoundError):
        r.get_signer("no-such")


def test_unknown_hasher_raises() -> None:
    r = AlgorithmRegistry()
    with pytest.raises(AlgorithmNotFoundError):
        r.get_hasher("no-such-hash")
