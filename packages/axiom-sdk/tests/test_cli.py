"""Tests for :mod:`axiom.cli`."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import yaml

from axiom.cli import main


def test_run_command_requires_api_key(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    from click.testing import CliRunner

    runner = CliRunner()
    env = {k: v for k, v in os.environ.items() if k != "AXIOM_API_KEY"}
    result = runner.invoke(main, ["run", str(script)], env=env)
    assert result.exit_code == 1
    assert "AXIOM_API_KEY" in result.output


def test_run_command_exits_on_missing_script() -> None:
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["run", "/nonexistent/nope.py"],
        env={**os.environ, "AXIOM_API_KEY": "k"},
    )
    assert result.exit_code != 0


def test_run_command_writes_report_file(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    out = tmp_path / "rep.json"
    from click.testing import CliRunner

    runner = CliRunner()
    with patch("axiom.cli.axiom.init"):
        result = runner.invoke(
            main,
            [
                "run",
                str(script),
                "--output",
                str(out),
            ],
            env={**os.environ, "AXIOM_API_KEY": "axm_test"},
        )
    assert result.exit_code == 0
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "summary" in data


def test_suggest_command_generates_yaml(tmp_path: Path) -> None:
    rep = tmp_path / "r.json"
    rep.write_text(
        json.dumps(
            {
                "agent_id": "a1",
                "calls": [],
                "total_calls": 0,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "p.yaml"
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(main, ["suggest", str(rep), "--output", str(out)])
    assert result.exit_code == 0
    assert out.is_file()
    body = "\n".join(
        line for line in out.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("#")
    )
    doc = yaml.safe_load(body)
    assert isinstance(doc, dict)
    assert "rules" in doc


def test_replay_command_compares_verdicts(tmp_path: Path) -> None:
    rep = tmp_path / "r.json"
    rep.write_text(
        json.dumps(
            {
                "calls": [
                    {
                        "action_type": "tool.http.read",
                        "target": "ex.com/",
                        "risk": "low",
                        "verdict": "allow",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    pol = tmp_path / "p.yaml"
    pol.write_text(
        "\n".join(
            [
                "name: t",
                "version: 1",
                "rules:",
                "  - name: deny-all",
                "    match: {}",
                "    verdict: deny",
            ]
        ),
        encoding="utf-8",
    )
    rout = tmp_path / "out.json"
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["replay", str(rep), "--policy", str(pol), "--output", str(rout)],
    )
    assert result.exit_code == 0
    payload = json.loads(rout.read_text(encoding="utf-8"))
    assert payload["changed_count"] >= 1
