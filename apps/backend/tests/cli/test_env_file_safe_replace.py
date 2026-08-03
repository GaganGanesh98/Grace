"""Unit tests for axiom.cli.envfile.replace_or_append."""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom.cli.envfile import read_env_value, replace_or_append


def test_append_when_key_absent(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_bytes(b"A=1\nB=2\nC=3\n")
    replace_or_append(p, "NEW", "x")
    assert p.read_bytes() == b"A=1\nB=2\nC=3\nNEW=x\n"


def test_replace_when_key_present(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    original = b"A=1\nAXIOM_WORKER_GATEWAY_API_KEY=old\nB=2\n"
    p.write_bytes(original)
    replace_or_append(p, "AXIOM_WORKER_GATEWAY_API_KEY", "newsecret")
    assert p.read_bytes() == b"A=1\nAXIOM_WORKER_GATEWAY_API_KEY=newsecret\nB=2\n"


def test_preserves_comments_and_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    original = b"# header\n\nFOO=bar\n\n"
    p.write_bytes(original)
    replace_or_append(p, "AXIOM_WORKER_GATEWAY_API_KEY", "k")
    assert p.read_bytes() == (
        b"# header\n\nFOO=bar\n\nAXIOM_WORKER_GATEWAY_API_KEY=k\n"
    )


@pytest.mark.parametrize(
    "bad",
    ["a\nb", "a\rb", "a\x00b"],
)
def test_rejects_secret_containing_newline_or_null(tmp_path: Path, bad: str) -> None:
    p = tmp_path / ".env"
    p.write_text("A=1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        replace_or_append(p, "AXIOM_WORKER_GATEWAY_API_KEY", bad)


def test_atomic_write_rollback_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / ".env"
    original = b"KEEP=1\n"
    p.write_bytes(original)

    real_replace = Path.replace

    def boom_replace(self: Path, target: str | Path) -> Path:
        t = Path(target)
        if t.name == ".env":
            raise OSError("simulated replace failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", boom_replace)
    with pytest.raises(OSError, match="simulated"):
        replace_or_append(p, "K", "v")
    assert p.read_bytes() == original


def test_read_env_value(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("X=1\n# comment\nY=\nZ=hello\n", encoding="utf-8")
    assert read_env_value(p, "X") == "1"
    assert read_env_value(p, "Y") == ""
    assert read_env_value(p, "Z") == "hello"
    assert read_env_value(p, "MISSING") is None
