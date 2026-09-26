"""GET /api/v1/providers — LLM provider catalog served from the provider registry."""

import json

import pytest
from httpx import AsyncClient

from axiom.gateway.protocol_handlers import normalize_model_prefix
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
async def test_curated_models_survive_the_qualify_then_strip_round_trip(
    client: AsyncClient,
) -> None:
    """The UI sends ``<service>/<model>``; the gateway must hand upstream the model back.

    Model ids are *not* required to be slash-free — Groq genuinely serves
    ``openai/gpt-oss-120b`` and ``groq/compound``. What has to hold is that
    prefixing with the service and then stripping one segment is the identity,
    because that is the path every model in this list actually takes.
    """
    tokens = await signup_user(client, unique_email(), "password1a")
    response = await client.get("/api/v1/providers", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200

    for item in response.json():
        for model in item["models"]:
            qualified = f"{item['service']}/{model}"
            body = json.dumps({"model": qualified}).encode()
            normalized = json.loads(normalize_model_prefix(body, item["service"]))
            assert normalized["model"] == model, (
                f"{item['service']}: {qualified} normalised to {normalized['model']!r}"
            )
        if item["models"]:
            assert item["default_model"] in item["models"]
        else:
            assert item["default_model"] == ""


@pytest.mark.asyncio
async def test_curated_models_are_unique_per_provider(client: AsyncClient) -> None:
    tokens = await signup_user(client, unique_email(), "password1a")
    response = await client.get("/api/v1/providers", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200

    for item in response.json():
        assert len(item["models"]) == len(set(item["models"])), item["service"]
