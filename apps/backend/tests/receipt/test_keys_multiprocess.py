"""Multiprocess signing-key convergence tests.

Validates that the preflight_ensure_keys() entrypoint eliminates the race
where two processes each auto-generate different keys against an empty .env.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PYTHON = sys.executable

_KEY_ENV_PREFIXES = (
    "AXIOM_ED25519_PRIVATE_PEM",
    "AXIOM_ED25519_PUBLIC_PEM",
    "AXIOM_ML_DSA_PRIVATE_B64",
    "AXIOM_ML_DSA_PUBLIC_B64",
    "AXIOM_EVIDENCE_KEY_B64",
)


def _subprocess_env(tmp_path: Path) -> dict[str, str]:
    """Build a clean env dict pointing REPO_ROOT at tmp_path.

    Explicitly blank-out all key env vars so pydantic-settings env vars
    override whatever the class-level env_file paths resolve to.
    """
    env = os.environ.copy()
    env["ENVIRONMENT"] = "development"
    env["DATABASE_URL"] = "sqlite://"
    env["REDIS_URL"] = "redis://localhost"
    env["SECRET_KEY"] = "test"
    env["JWT_SECRET"] = "test"
    env["ENCRYPTION_KEY"] = "test"
    for prefix in _KEY_ENV_PREFIXES:
        env.pop(prefix, None)
    return env


def _make_subprocess_script(tmp_path: Path, body: str) -> str:
    """Wrap body in the preamble that patches REPO_ROOT + Settings to use tmp .env."""
    return textwrap.dedent(f"""\
        import sys, pathlib, types
        _root = pathlib.Path({str(tmp_path)!r})

        import axiom.config as cfg
        cfg.REPO_ROOT = _root
        # Patch _env_files so a fresh Settings reads from the tmp .env only
        cfg._env_files = lambda: ({str(tmp_path / "apps" / "backend" / ".env")!r},)
        # Rebuild Settings class with patched env_file
        from pydantic_settings import SettingsConfigDict
        cfg.Settings.model_config["env_file"] = cfg._env_files()
        cfg.get_settings.cache_clear()

        import axiom.services.receipt.keys as keys_mod
        keys_mod.REPO_ROOT = _root
        keys_mod.reset_for_tests()
    """) + textwrap.dedent(body)


def _run_preflight_subprocess(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run preflight in a fresh subprocess, returning CompletedProcess."""
    script = _make_subprocess_script(tmp_path, """\
        ids = keys_mod.preflight_ensure_keys()
        print(ids["evidence_key_id"])
    """)
    return subprocess.run(
        [PYTHON, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _read_evidence_key_id_subprocess(tmp_path: Path, env: dict[str, str]) -> str:
    """Spawn a fresh subprocess that loads keys from .env and prints evidence_key_id."""
    script = _make_subprocess_script(tmp_path, """\
        k = keys_mod.get_signing_keys()
        print(k.evidence_key_id)
    """)
    result = subprocess.run(
        [PYTHON, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    return result.stdout.strip().splitlines()[-1]


def _setup_tmp_env(tmp_path: Path) -> None:
    """Create the directory structure that keys.py expects."""
    (tmp_path / "apps" / "backend").mkdir(parents=True)
    (tmp_path / "apps" / "backend" / ".env").touch()


def test_two_subprocesses_share_the_same_evidence_key(tmp_path: Path) -> None:
    """With preflight, two fresh subprocesses reading from .env converge."""
    _setup_tmp_env(tmp_path)
    env = _subprocess_env(tmp_path)

    # Run preflight — generates keys into tmp .env
    result = _run_preflight_subprocess(tmp_path, env)
    assert result.returncode == 0, f"preflight failed: {result.stderr}"
    preflight_id = result.stdout.strip().splitlines()[-1]

    dotenv = (tmp_path / "apps" / "backend" / ".env").read_text()
    for prefix in _KEY_ENV_PREFIXES:
        assert f"{prefix}=" in dotenv, f"{prefix} missing from .env after preflight"

    # Spawn two independent subprocesses that each read keys
    id_a = _read_evidence_key_id_subprocess(tmp_path, env)
    id_b = _read_evidence_key_id_subprocess(tmp_path, env)

    assert id_a == id_b, f"divergent keys: {id_a} vs {id_b}"
    assert id_a == preflight_id, f"subprocess key != preflight key: {id_a} vs {preflight_id}"


def test_preflight_is_idempotent(tmp_path: Path) -> None:
    """Second preflight on a populated .env must not rewrite keys."""
    _setup_tmp_env(tmp_path)
    env = _subprocess_env(tmp_path)

    # First preflight
    r1 = _run_preflight_subprocess(tmp_path, env)
    assert r1.returncode == 0, f"first preflight failed: {r1.stderr}"
    dotenv_after_first = (tmp_path / "apps" / "backend" / ".env").read_text()

    # Second preflight
    r2 = _run_preflight_subprocess(tmp_path, env)
    assert r2.returncode == 0, f"second preflight failed: {r2.stderr}"
    dotenv_after_second = (tmp_path / "apps" / "backend" / ".env").read_text()

    assert dotenv_after_first == dotenv_after_second, "idempotency violated: .env changed on second preflight"
    id1 = r1.stdout.strip().splitlines()[-1]
    id2 = r2.stdout.strip().splitlines()[-1]
    assert id1 == id2, "key IDs differ between preflight runs"


def test_preflight_refuses_in_production(tmp_path: Path) -> None:
    """In production with missing keys, preflight must fail."""
    _setup_tmp_env(tmp_path)
    env = _subprocess_env(tmp_path)
    env["ENVIRONMENT"] = "production"

    result = _run_preflight_subprocess(tmp_path, env)
    assert result.returncode != 0, "preflight should have failed in production"
    assert "Missing" in result.stderr or "MissingSigningKeysError" in result.stderr, (
        f"expected MissingSigningKeysError, got: {result.stderr}"
    )


def test_preflight_fails_fast_on_readonly_env(tmp_path: Path) -> None:
    """Unwritable .env must surface an explicit error, not silently fall back."""
    _setup_tmp_env(tmp_path)
    env_file = tmp_path / "apps" / "backend" / ".env"
    env_file.chmod(0o444)

    env = _subprocess_env(tmp_path)

    script = _make_subprocess_script(tmp_path, """\
        try:
            keys_mod.preflight_ensure_keys()
            sys.exit(0)
        except OSError as e:
            print(f"OSError: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected: {type(e).__name__}: {e}", file=sys.stderr)
            sys.exit(2)
    """)
    result = subprocess.run(
        [PYTHON, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    # Restore permissions for cleanup
    env_file.chmod(0o644)

    assert result.returncode != 0, "preflight should have failed on read-only .env"
