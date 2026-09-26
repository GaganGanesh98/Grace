"""Key inventory, backfill, rotation, and verification (Phase 8.2 Part 4).

    python -m axiom.cli.keys status
    python -m axiom.cli.keys migrate-vault --apply
    python -m axiom.cli.keys rotate --purpose vault --new-kek-b64 <b64> --apply
    python -m axiom.cli.keys verify

Or through the dev CLI: ``./axiom keys status``.

A rotation procedure first attempted during an incident is a rotation procedure
that fails, so every command here runs in --dry-run by default and prints what
it *would* do. Pass --apply to write. See docs/runbooks/key-rotation.md.

Nothing in this module prints key material or credential plaintext.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import sys

from axiom.db import session_scope
from axiom.services import vault_rotation
from axiom.services.crypto import kek_registry
from axiom.services.crypto.envelope import kek_fingerprint

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_USAGE = 2


def _out(line: str = "") -> None:
    print(line)


def _decode_kek(value: str) -> bytes:
    try:
        raw = base64.b64decode(value.strip().encode("ascii"), validate=True)
    except (binascii.Error, ValueError):
        raise SystemExit("--new-kek-b64 is not valid base64") from None
    if len(raw) != 32:
        raise SystemExit(f"--new-kek-b64 must decode to 32 bytes, got {len(raw)}")
    return raw


async def cmd_status() -> int:
    async with session_scope() as session:
        report = await vault_rotation.status(session)

    _out("purpose: vault")
    _out(f"  active kek_id : {report.active_kek_id}")
    _out(f"  known kek_ids : {', '.join(report.known_kek_ids)}")
    _out(f"  rows          : {report.total_rows}")
    if report.oldest_row_age_days is not None:
        _out(f"  oldest row    : {report.oldest_row_age_days:.1f} days")
    _out("  by scheme:")
    for scheme, count in sorted(report.rows_by_scheme.items()):
        _out(f"    {scheme:<20} {count}")
    _out("  by kek_id:")
    for kek_id, count in sorted(report.rows_by_kek_id.items()):
        marker = "  <- active" if kek_id == report.active_kek_id else ""
        _out(f"    {kek_id:<36} {count}{marker}")

    _out()
    if report.legacy_rows:
        _out(
            f"{report.legacy_rows} row(s) still on the legacy scheme. "
            "Run: axiom keys migrate-vault --apply",
        )
    else:
        _out("No legacy-scheme rows. Backfill is complete.")

    stale = {
        kek_id: count
        for kek_id, count in report.rows_by_kek_id.items()
        if kek_id not in {report.active_kek_id, "<none>"}
    }
    if stale:
        _out(
            f"{sum(stale.values())} row(s) still wrapped by a non-active KEK. "
            "A rotation is in progress or unfinished.",
        )
    return EXIT_OK


async def cmd_migrate_vault(*, apply: bool) -> int:
    async with session_scope() as session:
        result = await vault_rotation.backfill_legacy_rows(session, dry_run=not apply)

    mode = "APPLIED" if apply else "DRY RUN (pass --apply to write)"
    _out(f"migrate-vault — {mode}")
    _out(f"  legacy rows scanned : {result.scanned}")
    _out(f"  re-sealed as v2     : {result.resealed}")
    _out(f"  remaining legacy    : {result.remaining_legacy}")
    if result.failed:
        _out(f"  FAILED              : {len(result.failed)}")
        for row_id, reason in result.failed:
            _out(f"    {row_id}  {reason}")
        return EXIT_FAILURES
    return EXIT_OK


async def cmd_rotate(*, new_kek_b64: str, apply: bool) -> int:
    new_kek = _decode_kek(new_kek_b64)
    new_kek_id = kek_fingerprint(new_kek)

    active_key, active_id = kek_registry.active_kek(kek_registry.Purpose.VAULT)
    if active_key != new_kek:
        _out(
            "WARNING: the KEK passed here is not the configured active KEK "
            f"({active_id}). New writes will keep using the configured one. Set "
            "GRACE_VAULT_KEK_B64 to this key and restart before rotating, or "
            "rows will diverge.",
        )
        _out()

    async with session_scope() as session:
        before = await vault_rotation.status(session)
        result = await vault_rotation.rewrap_rows(
            session, new_kek=new_kek, new_kek_id=new_kek_id, dry_run=not apply
        )
        after = await vault_rotation.status(session)

    mode = "APPLIED" if apply else "DRY RUN (pass --apply to write)"
    _out(f"rotate --purpose vault — {mode}")
    _out(f"  target kek_id   : {new_kek_id}")
    _out(f"  rows scanned    : {result.scanned}")
    _out(f"  re-wrapped      : {result.rewrapped}")
    _out(f"  already current : {result.already_current}")
    _out(f"  before          : {before.rows_by_kek_id}")
    _out(f"  after           : {after.rows_by_kek_id}")
    if result.failed:
        _out(f"  FAILED          : {len(result.failed)}")
        for row_id, reason in result.failed:
            _out(f"    {row_id}  {reason}")
        return EXIT_FAILURES

    _out()
    _out("Next: axiom keys verify — then drop the old KEK from")
    _out("GRACE_VAULT_KEK_PREVIOUS_B64 once its row count reaches zero.")
    return EXIT_OK


async def cmd_verify() -> int:
    async with session_scope() as session:
        result = await vault_rotation.verify_rows(session)

    _out("verify --purpose vault")
    _out(f"  rows checked : {result.checked}")
    _out(f"  decryptable  : {result.ok}")
    if result.failed:
        _out(f"  FAILED       : {len(result.failed)}")
        for row_id, reason in result.failed:
            _out(f"    {row_id}  {reason}")
        return EXIT_FAILURES
    _out("  all rows decryptable")
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="axiom keys",
        description="Vault key inventory, backfill, rotation, and verification.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Active key, row counts by scheme and kek_id, oldest row.")

    migrate = sub.add_parser("migrate-vault", help="Re-seal legacy rows as grace/vault/v2.")
    migrate.add_argument("--apply", action="store_true", help="Write. Default is a dry run.")

    rotate = sub.add_parser("rotate", help="Re-wrap every row's DEK under a new KEK.")
    rotate.add_argument("--purpose", default="vault", choices=["vault"])
    rotate.add_argument("--new-kek-b64", required=True, help="Base64 of the new 32-byte KEK.")
    rotate.add_argument("--apply", action="store_true", help="Write. Default is a dry run.")

    verify = sub.add_parser("verify", help="Attempt an unseal of every row.")
    verify.add_argument("--purpose", default="vault", choices=["vault"])

    return parser


async def _async_main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "status":
        return await cmd_status()
    if args.cmd == "migrate-vault":
        return await cmd_migrate_vault(apply=args.apply)
    if args.cmd == "rotate":
        return await cmd_rotate(new_kek_b64=args.new_kek_b64, apply=args.apply)
    if args.cmd == "verify":
        return await cmd_verify()
    return EXIT_USAGE


def main() -> None:
    raise SystemExit(asyncio.run(_async_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
