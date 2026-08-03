"""Safe single-line update for shell-style .env files."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def _validate_value(value: str) -> None:
    if "\n" in value or "\r" in value or "\x00" in value:
        msg = "invalid env value: must not contain newline, carriage return, or NUL"
        raise ValueError(msg)


def read_env_value(path: Path, key: str) -> str | None:
    """Return the value for ``key`` from ``path``, or None if absent.

    Ignores ``#`` comment lines and lines that do not look like ``KEY=...``.
    """

    if not path.is_file():
        return None
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        k, _, rest = stripped.partition("=")
        if k.strip() != key:
            continue
        return rest
    return None


def replace_or_append(path: Path, key: str, value: str) -> None:
    """Replace one ``KEY=value`` line or append; atomic replace via temp + rename."""

    _validate_value(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_line = f"{key}={value}\n"

    if path.is_file():
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        out_lines: list[str] = []
        replaced = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, _ = stripped.partition("=")
                if k.strip() == key:
                    out_lines.append(new_line)
                    replaced = True
                    continue
            out_lines.append(line)
        if not replaced:
            if out_lines and not out_lines[-1].endswith("\n"):
                out_lines[-1] = out_lines[-1] + "\n"
            out_lines.append(new_line)
        body = "".join(out_lines).encode("utf-8")
    else:
        body = new_line.encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=".env.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        tmp_p = Path(tmp_name)
        tmp_p.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp_name).unlink(missing_ok=True)
        raise
