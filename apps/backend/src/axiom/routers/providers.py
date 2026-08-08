"""LLM provider catalog — read-only projection of the gateway provider registry.

Exists so the frontend does not keep a second copy of the provider/model list;
the registry stays the single source of truth (Phase 8.1 Part 3).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from axiom.deps import get_current_user
from axiom.gateway.provider_registry import PROVIDERS, get_provider_label
from axiom.models.user import User
from axiom.schemas.providers import ProviderCatalogItem

router = APIRouter()


@router.get("", response_model=list[ProviderCatalogItem])
async def list_providers(
    _user: Annotated[User, Depends(get_current_user)],
) -> list[ProviderCatalogItem]:
    """All registered providers, in registry (match-priority) order."""
    return [
        ProviderCatalogItem(
            service=spec.name,
            label=get_provider_label(spec),
            protocol=str(spec.protocol),
            models=list(spec.models),
            default_model=spec.default_model,
        )
        for spec in PROVIDERS.values()
    ]
