"""Inject decrypted provider credentials into outbound gateway requests."""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.models.agent_definition import AgentDefinition
from axiom.models.vault import VaultKey
from axiom.gateway.protocol_handlers import merge_forward_headers, prepare_upstream_request
from axiom.gateway.provider_registry import get_provider_spec
from axiom.services import vault as vault_service
from axiom.services.crypto import vault as aes_vault
from axiom.services.receipt.keys import get_signing_keys

logger = structlog.get_logger(__name__)


def _scrub_key_var(key: str) -> None:
    buf = bytearray(key.encode("utf-8"))
    for i in range(len(buf)):
        buf[i] = 0
    del buf


def _kek() -> bytes:
    return get_signing_keys().evidence_key


async def inject_credentials(
    db: AsyncSession,
    project_id: UUID,
    vault_user_id: UUID,
    provider: str,
    request_headers: dict[str, str],
    request_url: str,
    *,
    agent_id_header: str,
) -> tuple[dict[str, str], str, UUID]:
    """Decrypt vault key, build outbound headers + URL, and return the vault key id used."""
    prov = provider.lower()
    parsed_in = urlparse(request_url)
    logger.info(
        "gateway.inject.start",
        project_id=str(project_id),
        vault_user_id=str(vault_user_id),
        provider=prov,
        upstream_host=parsed_in.hostname,
        upstream_path=parsed_in.path,
    )
    spec = get_provider_spec(prov)
    if spec is None:
        logger.warning(
            "gateway.inject.unknown_provider",
            project_id=str(project_id),
            provider=prov,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_provider",
                "message": f"Provider {provider} is not configured in the provider registry",
            },
        )

    resolved: tuple[str, UUID] | None = None

    agent_uuid: UUID | None = None
    try:
        agent_uuid = UUID(agent_id_header)
    except ValueError:
        agent_uuid = None

    if agent_uuid is not None:
        ad = await db.scalar(
            select(AgentDefinition).where(
                AgentDefinition.project_id == project_id,
                AgentDefinition.agent_id == agent_uuid,
                AgentDefinition.is_archived.is_(False),
            )
        )
        if ad is not None:
            vk = await db.get(VaultKey, ad.vault_key_id)
            if (
                vk is not None
                and vk.is_active
                and vk.kind == "llm"
                and vk.service.lower() == prov
            ):
                raw = aes_vault.decrypt(vk.encrypted_key, _kek()).decode("utf-8")
                resolved = (raw, vk.id)
                logger.info(
                    "gateway.inject.used_agent_definition_vault_key",
                    vault_key_id=str(vk.id),
                    agent_id=str(agent_uuid),
                )

    if resolved is None:
        resolved = await vault_service.get_key_and_id_for_provider(db, vault_user_id, prov)

    logger.info(
        "gateway.inject.vault_lookup",
        project_id=str(project_id),
        provider=prov,
        found=resolved is not None,
    )
    if resolved is None:
        logger.warning(
            "gateway.inject.vault_missing",
            project_id=str(project_id),
            provider=prov,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": "vault_key_missing",
                "message": f"No {prov} key in vault. Add one in the dashboard.",
            },
        )
    raw_key, vault_key_id = resolved

    merged = merge_forward_headers(
        request_headers, provider_forward_headers=spec.forward_headers,
    )
    out_headers, out_url = prepare_upstream_request(spec, raw_key, request_url, merged)
    parsed_out = urlparse(out_url)
    logger.info(
        "gateway.inject.done",
        project_id=str(project_id),
        provider=prov,
        auth_method=str(spec.auth_method),
        vault_key_id=str(vault_key_id),
        has_authorization=bool(out_headers.get("Authorization") or out_headers.get("authorization")),
        has_x_api_key=bool(out_headers.get("x-api-key")),
        upstream_host=parsed_out.hostname,
        upstream_path=parsed_out.path,
    )

    try:
        _scrub_key_var(raw_key)
    except Exception:
        logger.exception("vault.scrub_failed")

    return out_headers, out_url, vault_key_id
