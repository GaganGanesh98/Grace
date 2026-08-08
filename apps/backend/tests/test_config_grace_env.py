"""GRACE_* / AXIOM_* environment aliases (Phase 8.2 Part 5, executing ADR-029)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from axiom.config import Settings, deprecated_env_vars, get_settings

REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:5433/db",
    "REDIS_URL": "redis://127.0.0.1:6380/1",
    "SECRET_KEY": "s" * 64,
    "JWT_SECRET": "j" * 32,
    "ENCRYPTION_KEY": "e" * 32,
}


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in {**REQUIRED, **env}.items():
        monkeypatch.setenv(key, value)
    return Settings()


class TestAliasPrecedence:
    def test_grace_wins_when_both_are_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(
            monkeypatch,
            GRACE_GATEWAY_PORT="9001",
            AXIOM_GATEWAY_PORT="8001",
        )
        assert settings.gateway_port == 9001

    def test_axiom_alone_still_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GRACE_GATEWAY_PORT", raising=False)
        settings = _settings(monkeypatch, AXIOM_GATEWAY_PORT="8123")
        assert settings.gateway_port == 8123

    def test_grace_alone_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AXIOM_GATEWAY_PORT", raising=False)
        settings = _settings(monkeypatch, GRACE_GATEWAY_PORT="8222")
        assert settings.gateway_port == 8222

    def test_unprefixed_legacy_spelling_still_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deployments that set the bare name must keep working."""
        for name in ("GRACE_CORS_ORIGINS", "AXIOM_CORS_ORIGINS"):
            monkeypatch.delenv(name, raising=False)
        settings = _settings(monkeypatch, BACKEND_CORS_ORIGINS='["https://example.com"]')
        assert settings.backend_cors_origins == ["https://example.com"]

    def test_grace_database_url_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        url = "postgresql+asyncpg://u:p@127.0.0.1:5433/other"
        monkeypatch.setenv("GRACE_DATABASE_URL", url)
        settings = _settings(monkeypatch)
        assert settings.database_url == url


class TestNewVariablesAreGraceOnly:
    @pytest.mark.parametrize(
        "field",
        ["grace_vault_kek_b64", "grace_vault_kek_id", "grace_vault_kek_previous_b64"],
    )
    def test_no_axiom_spelling(self, field: str) -> None:
        alias = Settings.model_fields[field].validation_alias
        names = list(getattr(alias, "choices", []))
        assert names and all(str(n).startswith("GRACE_") for n in names), names


class TestDeprecationReport:
    def test_lists_axiom_vars_still_set_with_their_replacement(self) -> None:
        found = deprecated_env_vars(
            {"AXIOM_GATEWAY_PORT": "1", "AXIOM_EVIDENCE_KEY_B64": "x", "PATH": "/bin"}
        )
        assert found == [
            ("AXIOM_EVIDENCE_KEY_B64", "GRACE_EVIDENCE_KEY_B64"),
            ("AXIOM_GATEWAY_PORT", "GRACE_GATEWAY_PORT"),
        ]

    def test_empty_when_only_grace_names_are_used(self) -> None:
        assert deprecated_env_vars({"GRACE_GATEWAY_PORT": "1", "PATH": "/bin"}) == []

    def test_every_axiom_alias_has_a_grace_replacement(self) -> None:
        """No setting may keep an AXIOM_* spelling without a GRACE_* successor."""
        orphans = []
        for name, field in Settings.model_fields.items():
            names = [str(n) for n in getattr(field.validation_alias, "choices", []) or []]
            if any(n.startswith("AXIOM_") for n in names) and not any(
                n.startswith("GRACE_") for n in names
            ):
                orphans.append(name)
        assert orphans == []
