"""Tests for RFC 8785 canonical JSON."""

from __future__ import annotations

import json

import pytest

from axiom.services.crypto.canonical_json import (
    NonCanonicalizableError,
    canonicalize,
    verify_canonical,
)


def test_canonicalize_empty_object() -> None:
    assert canonicalize({}) == b"{}"


def test_canonicalize_empty_array() -> None:
    assert canonicalize([]) == b"[]"


def test_canonicalize_nested() -> None:
    out = canonicalize({"b": 1, "a": {"z": 1, "y": 2}})
    assert out == b'{"a":{"y":2,"z":1},"b":1}'


def test_canonicalize_unicode() -> None:
    out = canonicalize({"ä": 1, "Z": 2})
    assert b'"Z"' in out
    assert out.index(b'"Z"') < out.index('"ä"'.encode())


def test_canonicalize_numbers() -> None:
    assert canonicalize(42) == b"42"
    assert canonicalize(1.25) == b"1.25"
    assert canonicalize(1.2e3) == b"1200"


def test_nan_infinity_rejected() -> None:
    with pytest.raises(NonCanonicalizableError):
        canonicalize(float("nan"))
    with pytest.raises(NonCanonicalizableError):
        canonicalize(float("inf"))


def test_bytes_not_allowed() -> None:
    with pytest.raises(TypeError):
        canonicalize(b"not-json")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        canonicalize(bytearray(b"x"))  # type: ignore[arg-type]


def test_round_trip() -> None:
    data = {"b": [None, True, 3], "a": {"x": "y"}}
    c = canonicalize(data)
    assert json.loads(c) == data


def test_verify_canonical_true() -> None:
    c = canonicalize({"a": 1})
    assert verify_canonical(c) is True


def test_verify_canonical_false_on_whitespace() -> None:
    assert verify_canonical(b'{ "a": 1 }') is False
