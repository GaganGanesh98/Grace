"""Auto-mint AXIOM project API key for the local agent worker (dev UX only)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.cli.envfile import read_env_value, replace_or_append
from axiom.config import REPO_ROOT, get_settings
from axiom.db import session_scope
from axiom.models.api_key import ApiKey
from axiom.models.project import Project
from axiom.models.user import User
from axiom.services.api_key import verify_key
from axiom.services.api_keys import create_api_key, revoke_api_key
from axiom.services.projects import create_project
from axiom.services.users import create_placeholder_user, get_user_by_email

logger = logging.getLogger("axiom.cli.automint")

BACKEND_ENV_PATH = REPO_ROOT / "apps" / "backend" / ".env"
DEV_USER_EMAIL = "dev-worker@local.axiom.internal"
DEV_PROJECT_SLUG = "axiom-dev"
DEV_PROJECT_NAME = "AXIOM Dev"
WORKER_KEY_NAME = "axiom-worker (auto-minted)"
WORKER_SCOPES = ["govern:write"]
ENV_KEY = "AXIOM_WORKER_GATEWAY_API_KEY"
AUTOMINT_FLAG = "AXIOM_WORKER_AUTOMINT"


def _is_ci() -> bool:
    ci = os.environ.get("CI", "").lower() == "true"
    gha = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    return ci or gha


def _short_prefix(key_prefix: str) -> str:
    return key_prefix[-4:] if len(key_prefix) >= 4 else key_prefix


def _explicit_shell_key() -> bool:
    return bool(os.environ.get(ENV_KEY, "").strip())


def _automint_disabled_in_file(env_path: Path) -> bool:
    raw = read_env_value(env_path, AUTOMINT_FLAG)
    if raw is None:
        return False
    return raw.strip() == "0"


async def _ensure_dev_user(session: AsyncSession) -> User:
    existing = await get_user_by_email(session, DEV_USER_EMAIL)
    if existing is not None:
        return existing
    return await create_placeholder_user(session, email=DEV_USER_EMAIL)


async def _ensure_dev_project(session: AsyncSession, owner: User) -> Project:
    row = await session.scalar(
        select(Project).where(
            Project.slug == DEV_PROJECT_SLUG,
            Project.deleted_at.is_(None),
            Project.owner_user_id == owner.id,
        )
    )
    if row is not None:
        return row
    return await create_project(
        session,
        owner=owner,
        name=DEV_PROJECT_NAME,
        description=None,
        slug=DEV_PROJECT_SLUG,
    )


async def _revoke_automint_keys(session: AsyncSession, project_id: UUID) -> None:
    rows = await session.scalars(
        select(ApiKey).where(
            ApiKey.project_id == project_id,
            ApiKey.name == WORKER_KEY_NAME,
            ApiKey.revoked_at.is_(None),
        )
    )
    for key in rows:
        await revoke_api_key(session, key)


async def ensure_worker_gateway_key(env_path: Path) -> str:
    """Return a short status token: ``skipped_ci``, ``skipped_explicit``, ``skipped_automint_off``,
    ``verified``, ``minted``, ``replaced``.
    """

    if _is_ci():
        logger.info("Auto-mint skipped (CI environment).")
        return "skipped_ci"
    if _explicit_shell_key():
        logger.info("Auto-mint skipped (explicit key provided).")
        return "skipped_explicit"
    if _automint_disabled_in_file(env_path):
        logger.info("Auto-mint skipped (AXIOM_WORKER_AUTOMINT=0).")
        return "skipped_automint_off"

    file_secret = read_env_value(env_path, ENV_KEY)
    secret = (file_secret or "").strip()

    async with session_scope() as session:
        user = await _ensure_dev_user(session)
        project = await _ensure_dev_project(session, user)

        if secret:
            ctx = await verify_key(session, secret, required_scope="govern:write")
            if ctx is not None and ctx.project_id == project.id:
                logger.info(
                    "Worker API key verified (prefix=%s...).",
                    _short_prefix(ctx.key_prefix),
                )
                return "verified"

            if secret:
                logger.info(
                    "Worker API key in .env is stale or revoked (prefix=%s). Re-minting.",
                    _short_prefix(secret[:16]) if len(secret) >= 16 else "????",
                )

        await _revoke_automint_keys(session, project.id)
        row, full = await create_api_key(
            session,
            project_id=project.id,
            name=WORKER_KEY_NAME,
            scopes=WORKER_SCOPES,
            created_by_user_id=user.id,
            expires_at=None,
        )

    replace_or_append(env_path, ENV_KEY, full)
    get_settings.cache_clear()

    logger.info(
        "Auto-minted worker API key for project %s (prefix=%s...). Stored in .env.",
        project.id,
        _short_prefix(row.key_prefix),
    )
    return "replaced" if secret else "minted"


async def rotate_worker_gateway_key(env_path: Path) -> tuple[str, str]:
    """Soft-revoke the current worker key, mint a new one, update ``env_path``.

    Returns ``(old_prefix_short, new_prefix_short)`` for logging (4-char suffixes).
    """

    if _is_ci():
        logger.info("rotate-worker-key skipped (CI environment).")
        return ("", "")

    file_secret = (read_env_value(env_path, ENV_KEY) or "").strip()
    if _explicit_shell_key() and not file_secret:
        logger.info("rotate-worker-key: explicit shell key in use; not managing .env.")
        return ("", "")

    secret = file_secret or os.environ.get(ENV_KEY, "").strip()

    async with session_scope() as session:
        user = await _ensure_dev_user(session)
        project = await _ensure_dev_project(session, user)

        old_prefix = "????"
        if secret:
            ctx = await verify_key(session, secret, required_scope="govern:write")
            if ctx is not None and ctx.project_id == project.id:
                row = await session.get(ApiKey, ctx.api_key_id)
                if row is not None:
                    old_prefix = _short_prefix(row.key_prefix)
                    await revoke_api_key(session, row)
            else:
                await _revoke_automint_keys(session, project.id)
        else:
            await _revoke_automint_keys(session, project.id)

        row, full = await create_api_key(
            session,
            project_id=project.id,
            name=WORKER_KEY_NAME,
            scopes=WORKER_SCOPES,
            created_by_user_id=user.id,
            expires_at=None,
        )
        new_prefix = _short_prefix(row.key_prefix)

    replace_or_append(env_path, ENV_KEY, full)
    get_settings.cache_clear()

    logger.info(
        "Rotated worker API key. Old prefix=%s..., new prefix=%s.... Restart ./axiom dev to apply.",
        old_prefix,
        new_prefix,
    )
    return (old_prefix, new_prefix)


async def _async_main() -> int:
    parser = argparse.ArgumentParser(prog="axiom.cli.automint")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ensure")
    sub.add_parser("rotate")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    env_path = BACKEND_ENV_PATH

    if args.cmd == "ensure":
        await ensure_worker_gateway_key(env_path)
        return 0
    if args.cmd == "rotate":
        await rotate_worker_gateway_key(env_path)
        return 0
    return 2


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
