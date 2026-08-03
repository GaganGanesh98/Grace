from __future__ import annotations

# ───────────────────────────────────────────────────────────────
# Namespace collision guard — backend vs SDK (both named "axiom").
# Same guard as tests/conftest.py. Proper fix: rename SDK to
# axiom_sdk in Phase 7.3.
# ───────────────────────────────────────────────────────────────
import sys
from pathlib import Path

_BACKEND_SRC = (Path(__file__).resolve().parent.parent / "src").as_posix()
if _BACKEND_SRC in sys.path:
    sys.path.remove(_BACKEND_SRC)
sys.path.insert(0, _BACKEND_SRC)

for _mod_name in list(sys.modules.keys()):
    if _mod_name == "axiom" or _mod_name.startswith("axiom."):
        _mod = sys.modules[_mod_name]
        _mod_file = getattr(_mod, "__file__", "") or ""
        if "axiom-sdk" in _mod_file:
            del sys.modules[_mod_name]
# ───────────────────────────────────────────────────────────────

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

import axiom.models  # noqa: F401
from axiom.config import get_settings
from axiom.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
