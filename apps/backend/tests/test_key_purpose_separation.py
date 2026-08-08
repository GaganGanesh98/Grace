"""The evidence key must not be reachable as a credential key (Phase 8.2 Part 3)."""

from __future__ import annotations

import base64
import secrets
from collections.abc import Iterator

import pytest

from axiom.config import get_settings
from axiom.services.crypto import kek_registry
from axiom.services.crypto.exceptions import KeyError_

EVIDENCE = secrets.token_bytes(32)


@pytest.fixture(autouse=True)
def _registered_evidence_key() -> Iterator[None]:
    kek_registry.reset_for_tests()
    kek_registry.set_evidence_key_provider(lambda: EVIDENCE)
    yield
    kek_registry.reset_for_tests()


@pytest.fixture
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_vault_kek_is_not_the_evidence_key() -> None:
    vault_key, _ = kek_registry.active_kek(kek_registry.Purpose.VAULT)
    evidence_key, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)
    assert vault_key != evidence_key


def test_vault_kek_ids_differ_from_the_evidence_key_id() -> None:
    _, vault_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)
    _, evidence_id = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)
    assert vault_id != evidence_id


def test_no_service_reads_the_evidence_key_to_encrypt_a_credential() -> None:
    """`services/vault.py` seals under the vault purpose only."""
    from axiom.services import vault as vault_service

    assert not hasattr(vault_service, "_encryption_key")

    from axiom.gateway import vault as gateway_vault

    assert not hasattr(gateway_vault, "_kek")


def test_purpose_separation_holds_when_kek_is_derived() -> None:
    """Derivation is the zero-config default; the guard must not fire on it."""
    kek_registry.assert_purpose_separation()


class TestExplicitKek:
    def test_explicit_kek_wins_and_passes_the_guard(
        self, monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
    ) -> None:
        explicit = secrets.token_bytes(32)
        monkeypatch.setenv("GRACE_VAULT_KEK_B64", base64.b64encode(explicit).decode())
        get_settings.cache_clear()

        key, _ = kek_registry.active_kek(kek_registry.Purpose.VAULT)
        assert key == explicit
        kek_registry.assert_purpose_separation()

    def test_derived_key_stays_readable_after_an_explicit_kek_is_set(
        self, monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
    ) -> None:
        """Rows sealed before the override was configured must still open."""
        derived_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)[1]

        monkeypatch.setenv(
            "GRACE_VAULT_KEK_B64", base64.b64encode(secrets.token_bytes(32)).decode()
        )
        get_settings.cache_clear()

        assert kek_registry.kek_by_id(
            kek_registry.Purpose.VAULT, derived_id
        ) == kek_registry.derive_vault_kek(EVIDENCE)

    def test_kek_equal_to_the_evidence_key_refuses_to_boot(
        self, monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
    ) -> None:
        monkeypatch.setenv("GRACE_VAULT_KEK_B64", base64.b64encode(EVIDENCE).decode())
        get_settings.cache_clear()

        with pytest.raises(KeyError_, match="byte-identical"):
            kek_registry.assert_purpose_separation()

    def test_explicit_kek_id_is_used_verbatim(
        self, monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
    ) -> None:
        """KMS key ids are not fingerprints of key material we hold."""
        monkeypatch.setenv(
            "GRACE_VAULT_KEK_B64", base64.b64encode(secrets.token_bytes(32)).decode()
        )
        monkeypatch.setenv("GRACE_VAULT_KEK_ID", "kms://grace/vault/3")
        get_settings.cache_clear()

        assert kek_registry.active_kek(kek_registry.Purpose.VAULT)[1] == "kms://grace/vault/3"

    def test_retired_keks_stay_resolvable(
        self, monkeypatch: pytest.MonkeyPatch, _clear_settings_cache: None
    ) -> None:
        retired = secrets.token_bytes(32)
        from axiom.services.crypto.envelope import kek_fingerprint

        monkeypatch.setenv(
            "GRACE_VAULT_KEK_B64", base64.b64encode(secrets.token_bytes(32)).decode()
        )
        monkeypatch.setenv(
            "GRACE_VAULT_KEK_PREVIOUS_B64", base64.b64encode(retired).decode()
        )
        get_settings.cache_clear()

        assert (
            kek_registry.kek_by_id(kek_registry.Purpose.VAULT, kek_fingerprint(retired))
            == retired
        )
