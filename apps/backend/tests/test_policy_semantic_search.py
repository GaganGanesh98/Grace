"""Semantic policy matching: pure helpers + the search endpoint end to end.

The embedding provider is replaced with a deterministic keyword one-hot embedder
so tests are fast and assertions are exact — no model download, no network.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from axiom.services.embeddings import service as emb
from axiom.services.policies import action_query_text, policy_embedding_text
from tests.conftest import auth_headers, signup_user, unique_email, unique_slug


class _KeywordEmbedder:
    """Maps text to a one-hot EMBEDDING_DIM vector by keyword, so cosine order
    is deterministic: delete→e0, read/log→e1, email/send→e2, else→e3."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * emb.EMBEDDING_DIM
        lowered = text.lower()
        if "delete" in lowered or "drop" in lowered:
            vector[0] = 1.0
        elif "read" in lowered or "select" in lowered or "log" in lowered:
            vector[1] = 1.0
        elif "email" in lowered or "send" in lowered:
            vector[2] = 1.0
        else:
            vector[3] = 1.0
        return vector


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(emb, "_get_provider", _KeywordEmbedder)
    emb.reset_provider()
    yield
    emb.reset_provider()


# --- pure helpers (no DB) ---------------------------------------------------


def test_policy_embedding_text_composes_name_description_rules() -> None:
    text = policy_embedding_text(
        "Prod Safety",
        "Protect production",
        [{"id": "r1", "description": "deny deletes of prod"}, {"id": "r2"}],
    )
    assert "Prod Safety" in text
    assert "Protect production" in text
    assert "deny deletes of prod" in text


def test_action_query_text_prefers_description() -> None:
    assert action_query_text({"description": "delete users", "tool": "sql"}) == "delete users"


def test_action_query_text_falls_back_to_scalars() -> None:
    assert "sql" in action_query_text({"tool": "sql", "rows": 5})


def test_action_query_text_non_dict() -> None:
    assert action_query_text([]) == ""  # type: ignore[arg-type]


# --- search endpoint (DB + pgvector) ----------------------------------------


async def _new_project(client: AsyncClient) -> tuple[str, dict[str, str]]:
    tokens = await signup_user(client, unique_email(), "password1a")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post(
        "/api/v1/projects", headers=headers, json={"name": "S", "slug": unique_slug("s")}
    )
    return resp.json()["data"]["id"], headers


async def _create_policy(
    client: AsyncClient, pid: str, headers: dict[str, str], **kw: object
) -> None:
    resp = await client.post(f"/api/v1/projects/{pid}/policies", headers=headers, json=kw)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_search_ranks_by_semantic_meaning(client: AsyncClient) -> None:
    pid, headers = await _new_project(client)
    await _create_policy(
        client, pid, headers,
        slug=unique_slug("del"), name="Deletion guardrail",
        description="deny delete of production data", rules=[],
    )
    await _create_policy(
        client, pid, headers,
        slug=unique_slug("read"), name="Log reader",
        description="allow read of application logs", rules=[],
    )

    resp = await client.get(
        f"/api/v1/projects/{pid}/policies/search",
        headers=headers,
        params={"q": "agent wants to delete the users table", "k": 5},
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["data"]
    assert len(results) == 2
    # The deletion policy is semantically closest to a delete action.
    assert results[0]["policy"]["name"] == "Deletion guardrail"
    assert results[0]["similarity"] == pytest.approx(1.0, abs=1e-4)
    assert results[0]["similarity"] > results[1]["similarity"]


@pytest.mark.asyncio
async def test_search_scopes_to_project(client: AsyncClient) -> None:
    pid_a, headers_a = await _new_project(client)
    await _create_policy(
        client, pid_a, headers_a,
        slug=unique_slug("del"), name="Deletion guardrail",
        description="deny delete of production data", rules=[],
    )
    pid_b, headers_b = await _new_project(client)
    resp = await client.get(
        f"/api/v1/projects/{pid_b}/policies/search",
        headers=headers_b,
        params={"q": "delete the users table"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient) -> None:
    pid, headers = await _new_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/policies/search", headers=headers)
    assert resp.status_code == 422
