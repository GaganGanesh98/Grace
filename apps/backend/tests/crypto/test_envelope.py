"""Envelope encryption + KEK resolution (Phase 8.2 Part 1)."""

from __future__ import annotations

import secrets
from uuid import uuid4

import pytest

from axiom.services.crypto import envelope, kek_registry
from axiom.services.crypto.exceptions import CryptoInputError, DecryptionError, KeyError_

PLAINTEXT = b"sk-ant-not-a-real-key"


def _kek() -> bytes:
    return secrets.token_bytes(32)


def _aad() -> bytes:
    return envelope.vault_aad(uuid4(), uuid4())


class TestSealUnseal:
    def test_round_trip(self) -> None:
        kek = _kek()
        aad = _aad()
        sealed = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=aad)
        assert envelope.unseal(sealed, kek, aad=aad) == PLAINTEXT

    def test_records_scheme_and_key_id(self) -> None:
        sealed = envelope.seal(PLAINTEXT, _kek(), kek_id="k1", aad=_aad())
        assert sealed.scheme == envelope.SCHEME_V2
        assert sealed.kek_id == "k1"
        assert sealed.wrapped_dek

    def test_wrong_kek_fails_closed(self) -> None:
        aad = _aad()
        sealed = envelope.seal(PLAINTEXT, _kek(), kek_id="k1", aad=aad)
        with pytest.raises(DecryptionError):
            envelope.unseal(sealed, _kek(), aad=aad)

    def test_wrong_aad_fails(self) -> None:
        """A ciphertext from row A must not open as row B."""
        kek = _kek()
        user_id = uuid4()
        row_a = envelope.vault_aad(uuid4(), user_id)
        row_b = envelope.vault_aad(uuid4(), user_id)
        sealed = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=row_a)
        with pytest.raises(DecryptionError):
            envelope.unseal(sealed, kek, aad=row_b)

    def test_cross_user_aad_fails(self) -> None:
        kek = _kek()
        vault_key_id = uuid4()
        as_user_a = envelope.vault_aad(vault_key_id, uuid4())
        as_user_b = envelope.vault_aad(vault_key_id, uuid4())
        sealed = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=as_user_a)
        with pytest.raises(DecryptionError):
            envelope.unseal(sealed, kek, aad=as_user_b)

    def test_wrapped_dek_bound_to_kek_id(self) -> None:
        """Relabelling a row's kek_id must not let the DEK unwrap."""
        kek = _kek()
        aad = _aad()
        sealed = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=aad)
        relabelled = envelope.WrappedSecret(
            kek_id="k2",
            scheme=sealed.scheme,
            wrapped_dek=sealed.wrapped_dek,
            ciphertext=sealed.ciphertext,
        )
        with pytest.raises(DecryptionError):
            envelope.unseal(relabelled, kek, aad=aad)

    def test_identical_plaintext_produces_different_ciphertext(self) -> None:
        kek = _kek()
        aad = _aad()
        first = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=aad)
        second = envelope.seal(PLAINTEXT, kek, kek_id="k1", aad=aad)
        assert first.ciphertext != second.ciphertext
        assert first.wrapped_dek != second.wrapped_dek

    def test_rejects_empty_plaintext_and_short_kek(self) -> None:
        with pytest.raises(CryptoInputError):
            envelope.seal(b"", _kek(), kek_id="k1", aad=_aad())
        with pytest.raises(CryptoInputError):
            envelope.seal(PLAINTEXT, b"short", kek_id="k1", aad=_aad())
        with pytest.raises(CryptoInputError):
            envelope.seal(PLAINTEXT, _kek(), kek_id="  ", aad=_aad())

    def test_rejects_unknown_scheme(self) -> None:
        sealed = envelope.seal(PLAINTEXT, _kek(), kek_id="k1", aad=_aad())
        legacy = envelope.WrappedSecret(
            kek_id=sealed.kek_id,
            scheme=envelope.SCHEME_LEGACY,
            wrapped_dek=sealed.wrapped_dek,
            ciphertext=sealed.ciphertext,
        )
        with pytest.raises(CryptoInputError):
            envelope.unseal(legacy, _kek(), aad=_aad())


class TestRewrap:
    def test_ciphertext_is_byte_identical(self) -> None:
        """The guarantee that keeps rotation cheap. Do not relax this test."""
        old, new = _kek(), _kek()
        aad = _aad()
        sealed = envelope.seal(PLAINTEXT, old, kek_id="old", aad=aad)
        rotated = envelope.rewrap(sealed, old, new, new_kek_id="new")
        assert rotated.ciphertext == sealed.ciphertext
        assert rotated.wrapped_dek != sealed.wrapped_dek
        assert rotated.kek_id == "new"

    def test_plaintext_recoverable_under_new_kek_only(self) -> None:
        old, new = _kek(), _kek()
        aad = _aad()
        sealed = envelope.seal(PLAINTEXT, old, kek_id="old", aad=aad)
        rotated = envelope.rewrap(sealed, old, new, new_kek_id="new")

        assert envelope.unseal(rotated, new, aad=aad) == PLAINTEXT
        with pytest.raises(DecryptionError):
            envelope.unseal(rotated, old, aad=aad)

    def test_wrong_old_kek_fails(self) -> None:
        old, new = _kek(), _kek()
        sealed = envelope.seal(PLAINTEXT, old, kek_id="old", aad=_aad())
        with pytest.raises(DecryptionError):
            envelope.rewrap(sealed, _kek(), new, new_kek_id="new")


class TestFingerprint:
    def test_deterministic_and_distinct(self) -> None:
        kek = _kek()
        assert envelope.kek_fingerprint(kek) == envelope.kek_fingerprint(kek)
        assert envelope.kek_fingerprint(kek) != envelope.kek_fingerprint(_kek())

    def test_is_not_the_key(self) -> None:
        kek = _kek()
        assert kek.hex() not in envelope.kek_fingerprint(kek)


class TestDerivation:
    def test_deterministic(self) -> None:
        ikm = _kek()
        assert kek_registry.derive_vault_kek(ikm) == kek_registry.derive_vault_kek(ikm)

    def test_differs_from_input_key_material(self) -> None:
        ikm = _kek()
        derived = kek_registry.derive_vault_kek(ikm)
        assert derived != ikm
        assert len(derived) == 32

    def test_distinct_per_input(self) -> None:
        assert kek_registry.derive_vault_kek(_kek()) != kek_registry.derive_vault_kek(_kek())

    def test_rejects_wrong_length(self) -> None:
        with pytest.raises(CryptoInputError):
            kek_registry.derive_vault_kek(b"too short")


class TestRegistry:
    @pytest.fixture(autouse=True)
    def _isolate(self) -> None:
        kek_registry.reset_for_tests()

    def test_vault_kek_derives_from_evidence_key_when_unset(self) -> None:
        evidence = _kek()
        kek_registry.set_evidence_key_provider(lambda: evidence)

        key, kek_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)
        assert key == kek_registry.derive_vault_kek(evidence)
        assert key != evidence
        assert kek_id == envelope.kek_fingerprint(key)

    def test_read_resolves_by_recorded_id(self) -> None:
        evidence = _kek()
        kek_registry.set_evidence_key_provider(lambda: evidence)

        key, kek_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)
        assert kek_registry.kek_by_id(kek_registry.Purpose.VAULT, kek_id) == key

    def test_unknown_kek_id_raises_rather_than_guessing(self) -> None:
        kek_registry.set_evidence_key_provider(_kek)
        with pytest.raises(KeyError_):
            kek_registry.kek_by_id(kek_registry.Purpose.VAULT, "not-a-real-id")

    def test_evidence_purpose_returns_the_evidence_key(self) -> None:
        evidence = _kek()
        kek_registry.set_evidence_key_provider(lambda: evidence)
        key, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)
        assert key == evidence

    def test_vault_and_evidence_keks_differ(self) -> None:
        kek_registry.set_evidence_key_provider(lambda: b"e" * 32)
        vault, _ = kek_registry.active_kek(kek_registry.Purpose.VAULT)
        evidence, _ = kek_registry.active_kek(kek_registry.Purpose.EVIDENCE)
        assert vault != evidence
