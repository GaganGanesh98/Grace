"""AXIOM CLI — ``axiom run``, ``axiom suggest``, ``axiom replay``."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
import yaml

import axiom
from axiom.exceptions import GovernanceDenied, GovernanceHeld
from axiom.interceptor import HttpInterceptor
from axiom.policy_suggester import evaluate_policy, suggest_policy
from axiom.recorder import GovernanceRecorder


def _print_run_summary(
    *,
    agent_id: str,
    mode: str,
    recorder: GovernanceRecorder,
    report_path: Path,
    learn_hint: bool,
) -> None:
    click.echo(f"\n{'=' * 60}")
    click.echo("AXIOM Governance Report")
    click.echo(f"{'=' * 60}")
    click.echo(f"Agent:     {agent_id}")
    click.echo(f"Mode:      {mode}")
    click.echo(f"Total calls intercepted: {recorder.total_calls}")
    click.echo(f"  Allowed: {recorder.allowed_count}")
    click.echo(f"  Denied:  {recorder.denied_count}")
    click.echo(f"  Held:    {recorder.held_count}")
    click.echo(f"  Errors:  {recorder.error_count}")
    click.echo(f"Report:    {report_path}")
    if learn_hint and mode == "learn":
        click.echo("\n💡 To generate a policy from this run:")
        click.echo(f"   axiom suggest {report_path}")


@click.group()
@click.version_option(axiom.__version__, prog_name="axiom")
def main() -> None:
    """AXIOM — govern Python agents with zero code changes."""


@main.command("run")
@click.option("--mode", type=click.Choice(["learn", "enforce"]), default="learn")
@click.option("--agent-id", "agent_id", default=None, help="Agent id (default: script filename)")
@click.option("--workflow", default=None, help="Optional workflow / chain name")
@click.option(
    "--policy",
    "policy_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Policy YAML path (recorded in report; server-side policy still applies to govern API)",
)
@click.option("--max-cost", type=float, default=None, help="Max LLM spend (USD) before stop")
@click.option("--max-runtime", type=float, default=None, help="Max execution time (seconds)")
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    default=Path("./axiom_report.json"),
    help="Governance report JSON path",
)
@click.option("--verbose", is_flag=True, help="Print each governance decision")
@click.argument("script", type=click.Path(path_type=Path, exists=True))
@click.argument("script_args", nargs=-1)
def run_command(
    mode: str,
    agent_id: str | None,
    workflow: str | None,
    policy_path: Path | None,
    max_cost: float | None,
    max_runtime: float | None,
    output: Path,
    verbose: bool,
    script: Path,
    script_args: tuple[str, ...],
) -> None:
    """Run a Python script with HTTP governance interception."""
    api_key = os.environ.get("AXIOM_API_KEY")
    if not api_key:
        click.echo("Error: AXIOM_API_KEY environment variable required", err=True)
        click.echo("Get your key at https://axiom.dev/dashboard/projects", err=True)
        raise SystemExit(1)

    axiom.init(api_key=api_key)

    script_path = script.resolve()
    aid = agent_id or script_path.name

    recorder = GovernanceRecorder(agent_id=aid)
    interceptor = HttpInterceptor(
        agent_id=aid,
        mode=mode,
        recorder=recorder,
        workflow=workflow,
        max_cost=max_cost,
        max_runtime=max_runtime,
        verbose=verbose,
    )
    interceptor.install()

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(script_path)] + list(script_args)
        sys.path.insert(0, str(script_path.parent))
        script_globals: dict[str, Any] = {
            "__name__": "__main__",
            "__file__": str(script_path),
        }
        if verbose:
            click.echo(f"[axiom] Running with mode={mode} agent_id={aid}", err=True)
        exec(compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec"), script_globals)
    except GovernanceDenied as e:
        click.echo(f"\n🛑 Agent action DENIED: {e.reason}", err=True)
    except GovernanceHeld as e:
        click.echo(f"\n⏸  Agent action HELD (receipt: {e.receipt_id})", err=True)
    except ConnectionError as e:
        click.echo(f"\n🛑 {e}", err=True)
    except KeyboardInterrupt:
        click.echo("\n⚡ Interrupted by user", err=True)
    except Exception as e:
        click.echo(f"\n❌ Script error: {e}", err=True)
    finally:
        sys.argv = old_argv
        interceptor.uninstall()
        report = recorder.finalize()
        if policy_path is not None:
            report["policy_path"] = str(policy_path.resolve())
        if workflow:
            report["workflow"] = workflow
        report_path = Path(output)
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        _print_run_summary(
            agent_id=aid,
            mode=mode,
            recorder=recorder,
            report_path=report_path.resolve(),
            learn_hint=True,
        )


@main.command("suggest")
@click.argument("report_json", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    default=Path("./axiom_policy.yaml"),
    help="Suggested policy YAML output path",
)
def suggest_command(report_json: Path, output: Path) -> None:
    """Generate policy YAML from a learning-run report."""
    raw = Path(report_json).read_text(encoding="utf-8")
    report = json.loads(raw)
    yaml_out = suggest_policy(report)
    out_path = Path(output)
    out_path.write_text(yaml_out, encoding="utf-8")
    click.echo(f"Wrote suggested policy to {out_path.resolve()}")


@main.command("replay")
@click.argument("report_json", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--policy",
    "policy_path",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Policy YAML to evaluate against",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    default=Path("./axiom_replay.json"),
    help="Replay results JSON path",
)
def replay_command(report_json: Path, policy_path: Path, output: Path) -> None:
    """Replay recorded calls against a policy (no agent re-run)."""
    report = json.loads(Path(report_json).read_text(encoding="utf-8"))
    policy = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise click.ClickException("Policy file must contain a YAML mapping at the root")

    calls = report.get("calls") or []
    results: list[dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        original_verdict = str(call.get("verdict") or "")
        action_type = str(call.get("action_type") or "")
        target = str(call.get("target") or "")
        risk = str(call.get("risk") or "low")
        new_verdict = evaluate_policy(policy, action_type, target, risk)
        row = {**call, "original_verdict": original_verdict, "replay_verdict": new_verdict}
        row["changed"] = original_verdict != new_verdict
        results.append(row)

    changed = [r for r in results if r.get("changed")]
    out_payload = {
        "policy": str(Path(policy_path).resolve()),
        "report": str(Path(report_json).resolve()),
        "results": results,
        "changed_count": len(changed),
    }
    Path(output).write_text(json.dumps(out_payload, indent=2, default=str), encoding="utf-8")

    click.echo(f"Replayed {len(results)} calls against {policy_path}")
    click.echo(f"  Changed verdicts: {len(changed)}")
    for r in changed:
        click.echo(
            f"    {r.get('action_type')} → {r.get('target')}: "
            f"{r.get('original_verdict')} → {r.get('replay_verdict')}"
        )
    click.echo(f"Wrote replay results to {Path(output).resolve()}")


if __name__ == "__main__":
    main()
