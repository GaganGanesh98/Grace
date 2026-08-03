"""Phase-2 signing-key loader tests (autogen in dev; refuse in prod)."""

from __future__ import annotations

import base64

import pytest
from pydantic import SecretStr

from axiom.config import get_settings
from axiom.services.receipt import keys as keys_mod
from axiom.services.receipt.keys import (
    MissingSigningKeysError,
    _b64encode,
    _from_settings,
    _is_dev_or_test,
    _missing_fields,
    export_b64,
    get_signing_keys,
    reset_for_tests,
)


def test_is_dev_or_test() -> None:
    assert _is_dev_or_test("development") is True
    assert _is_dev_or_test("TEST") is True
    assert _is_dev_or_test("local") is True
    assert _is_dev_or_test("production") is False


def test_missing_fields_lists_empty_env() -> None:
    class _Empty:
        axiom_ed25519_private_pem = None
        axiom_ed25519_public_pem = None
        axiom_ml_dsa_private_b64 = None
        axiom_ml_dsa_public_b64 = None
        axiom_evidence_key_b64 = None

    missing = _missing_fields(_Empty())
    assert len(missing) == 5


def test_missing_fields_treats_empty_string_as_missing() -> None:
    class _Empty:
        axiom_ed25519_private_pem = SecretStr("")
        axiom_ed25519_public_pem = ""
        axiom_ml_dsa_private_b64 = None
        axiom_ml_dsa_public_b64 = None
        axiom_evidence_key_b64 = None

    missing = _missing_fields(_Empty())
    assert "AXIOM_ED25519_PUBLIC_PEM" in missing


def test_get_signing_keys_autogen_cached() -> None:
    reset_for_tests()
    a = get_signing_keys()
    b = get_signing_keys()
    assert a is b
    assert len(a.evidence_key) == 32


def test_export_b64_roundtrip() -> None:
    reset_for_tests()
    k = get_signing_keys()
    exported = export_b64(k)
    assert exported["AXIOM_ED25519_PRIVATE_PEM"].startswith("-----BEGIN PRIVATE KEY-----")
    assert (
        base64.b64decode(exported["AXIOM_ML_DSA_PRIVATE_B64"])
        == k.ml_dsa_private.get_secret_value()
    )
    assert base64.b64decode(exported["AXIOM_EVIDENCE_KEY_B64"]) == k.evidence_key


def test_b64encode_helper() -> None:
    assert _b64encode(b"\x00\x01\x02") == base64.b64encode(b"\x00\x01\x02").decode("ascii")


def test_from_settings_loads_pinned_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_for_tests()
    pre = get_signing_keys()
    exported = export_b64(pre)
    reset_for_tests()

    s = get_settings()
    monkeypatch.setattr(
        s, "axiom_ed25519_private_pem", SecretStr(exported["AXIOM_ED25519_PRIVATE_PEM"])
    )
    monkeypatch.setattr(s, "axiom_ed25519_public_pem", exported["AXIOM_ED25519_PUBLIC_PEM"])
    monkeypatch.setattr(
        s, "axiom_ml_dsa_private_b64", SecretStr(exported["AXIOM_ML_DSA_PRIVATE_B64"])
    )
    monkeypatch.setattr(s, "axiom_ml_dsa_public_b64", exported["AXIOM_ML_DSA_PUBLIC_B64"])
    monkeypatch.setattr(s, "axiom_evidence_key_b64", SecretStr(exported["AXIOM_EVIDENCE_KEY_B64"]))

    loaded = _from_settings()
    assert loaded.evidence_key == pre.evidence_key
    assert loaded.ed25519_public == pre.ed25519_public


def test_from_settings_rejects_wrong_evidence_key_length(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_for_tests()
    s = get_settings()
    monkeypatch.setattr(s, "axiom_ed25519_private_pem", SecretStr("x"))
    monkeypatch.setattr(s, "axiom_ed25519_public_pem", "y")
    monkeypatch.setattr(
        s,
        "axiom_ml_dsa_private_b64",
        SecretStr(base64.b64encode(b"\x00" * 100).decode()),
    )
    monkeypatch.setattr(s, "axiom_ml_dsa_public_b64", base64.b64encode(b"\x00" * 100).decode())
    # 16 bytes instead of 32
    monkeypatch.setattr(
        s,
        "axiom_evidence_key_b64",
        SecretStr(base64.b64encode(b"\x00" * 16).decode()),
    )

    with pytest.raises(ValueError, match="AES-256-GCM"):
        _from_settings()


def test_production_missing_keys_refuses_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_for_tests()
    s = get_settings()
    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "axiom_ed25519_private_pem", None)
    monkeypatch.setattr(s, "axiom_ed25519_public_pem", None)
    monkeypatch.setattr(s, "axiom_ml_dsa_private_b64", None)
    monkeypatch.setattr(s, "axiom_ml_dsa_public_b64", None)
    monkeypatch.setattr(s, "axiom_evidence_key_b64", None)
    keys_mod._cache = None

    with pytest.raises(MissingSigningKeysError):
        get_signing_keys()
    reset_for_tests()
