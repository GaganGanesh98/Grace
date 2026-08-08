"""GET /api/v1/providers — LLM provider catalog served from the provider registry."""

import pytest
from httpx import AsyncClient

from axiom.gateway.provider_registry import PROVIDERS
from tests.conftest import auth_headers, signup_user, unique_email


@pytest.mark.asyncio
async def test_providers_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/providers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_providers_mirror_the_registry(client: AsyncClient) -> None:
    tokens = await signup_user(client, unique_email(), "password1a")
    response = await client.get("/api/v1/providers", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200, response.text

    items = response.json()
    assert [i["service"] for i in items] == list(PROVIDERS.keys())

    by_service = {i["service"]: i for i in items}
    for name, spec in PROVIDERS.items():
        assert by_service[name]["models"] == list(spec.models)
        assert by_service[name]["default_model"] == spec.default_model
        assert by_service[name]["label"] == (spec.label or spec.name)


@pytest.mark.asyncio
async def test_curated_models_are_bare_ids_and_include_their_default(client: AsyncClient) -> None:
    """The gateway strips a ``provider/`` prefix, so the registry stores bare ids."""
    tokens = await signup_user(client, unique_email(), "password1a")
    response = await client.get("/api/v1/providers", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200

    for item in response.json():
        for model in item["models"]:
            assert "/" not in model, f"{item['service']} model {model} must not carry a prefix"
        if item["models"]:
            assert item["default_model"] in item["models"]
        else:
            assert item["default_model"] == ""
