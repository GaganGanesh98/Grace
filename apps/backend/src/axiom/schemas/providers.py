"""Response models for /api/v1/providers (Phase 8.1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProviderCatalogItem(BaseModel):
    """One LLM provider as the UI needs it: identity plus its known model ids."""

    model_config = ConfigDict(frozen=True)

    service: str
    label: str
    protocol: str
    #: Model ids as the provider names them upstream, without a ``provider/`` prefix.
    #: Empty when the registry has no curated list — the UI falls back to free text.
    models: list[str]
    #: Preferred model id for new agents, or "" when there is no curated list.
    default_model: str
