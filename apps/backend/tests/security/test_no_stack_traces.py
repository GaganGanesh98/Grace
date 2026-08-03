import pytest
from httpx import AsyncClient

from axiom.services import projects as projects_service
from tests.conftest import auth_headers, signup_user, unique_email


@pytest.mark.asyncio
@pytest.mark.security
async def test_unhandled_error_response_has_no_traceback(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = unique_email()
    tokens = await signup_user(client, email, "password1a")

    async def boom(*args: object, **kwargs: object) -> tuple[list[object], int]:
        raise RuntimeError("SECRET_TRACEBACK_MARKER")

    monkeypatch.setattr(projects_service, "list_projects_for_user", boom)

    response = await client.get(
        "/api/v1/projects",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 500
    text = response.text.lower()
    assert "secret_traceback_marker" not in text
    assert "traceback" not in text
