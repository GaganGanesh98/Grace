import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_openapi_paths_have_tags(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    paths = spec.get("paths", {})
    missing: list[str] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, meta in methods.items():
            if method not in {"get", "post", "put", "patch", "delete", "head"}:
                continue
            if not isinstance(meta, dict):
                continue
            tags = meta.get("tags")
            if not tags:
                missing.append(f"{method.upper()} {path}")
    assert not missing, "Operations missing OpenAPI tags:\n" + "\n".join(missing)
