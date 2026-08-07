"""FastAPI app for the governance gateway (separate process / port)."""

from __future__ import annotations

import hashlib
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import unquote, urlparse
from uuid import UUID

import httpx
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.db import get_db, session_scope
from axiom.gateway.classifier import (
    GatewayClassification,
    agent_id_from_headers,
    classify_gateway_request,
    parse_stream_flag,
)
from axiom.gateway.middleware import authenticate_gateway_request, check_gateway_rate_limit
from axiom.gateway.pipeline import (
    run_gateway_governance,
    seal_after_success,
    seal_after_transport_failure,
)
from axiom.gateway.protocol_handlers import (
    build_upstream_url,
    normalize_model_prefix,
    sanitize_upstream_response_headers,
)
from axiom.gateway.provider_registry import get_provider_spec
from axiom.gateway.proxy import (
    assert_public_http_url,
    open_streaming_response,
    proxy_request,
)
from axiom.gateway.upstream_audit import build_upstream_audit
from axiom.gateway.vault import inject_credentials
from axiom.middleware.body_size import BodySizeLimitMiddleware
from axiom.services import vault as vault_service
from axiom.services.api_key import APIKeyContext
from axiom.services.governance.receipt import load_governance_merkle_from_db
from axiom.services.redis_client import close_redis

logger = structlog.get_logger(__name__)
_settings = get_settings()


def _preview_upstream_error(content: bytes, limit: int = 2048) -> str:
    return content[:limit].decode("utf-8", errors="replace")


def _http_client_for(request: Request) -> httpx.AsyncClient:
    """Return shared outbound client.

    Lazy-init when ASGI lifespan did not run (e.g. httpx ASGITransport tests).
    """
    if getattr(request.app.state, "http_client", None) is None:
        request.app.state.http_client = httpx.AsyncClient()
    return request.app.state.http_client


def _headers_to_str_dict(request: Request) -> dict[str, str]:
    return {str(k): str(v) for k, v in request.headers.items()}


async def _read_body_limit(request: Request, max_bytes: int) -> bytes:
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > max_bytes:
                raise ValueError
        except ValueError as exc:
            raise ValueError from exc
    body = await request.body()
    if len(body) > max_bytes:
        raise ValueError
    return body


def _json_error(
    status_code: int,
    body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body, headers=headers or {})


async def _run_governed_proxy(
    *,
    request: Request,
    db: AsyncSession,
    api_ctx: APIKeyContext,
    provider: str,
    outbound_url: str,
    path_for_classify: str,
    body: bytes,
) -> Response:
    classification = classify_gateway_request(
        provider,
        request.method,
        path_for_classify,
        body,
        outbound_url=outbound_url,
    )
    agent_id = agent_id_from_headers(request.headers)
    gov = await run_gateway_governance(
        db,
        project_id=api_ctx.project_id,
        classification=classification,
        agent_id=agent_id,
    )
    logger.info(
        "gateway.governance.result",
        project_id=str(api_ctx.project_id),
        provider=provider,
        verdict=gov.kind,
    )

    receipt_id = (
        gov.deny.receipt_id
        if gov.deny
        else gov.hold.receipt_id
        if gov.hold
        else gov.allow.receipt_id
        if gov.allow
        else None
    )
    assert receipt_id is not None
    hdr_receipt = {"X-Axiom-Receipt-Id": str(receipt_id)}

    if gov.kind == "deny":
        return _json_error(
            status.HTTP_403_FORBIDDEN,
            {"error": "governance_denied", "receipt_id": str(receipt_id)},
            headers=hdr_receipt,
        )

    if gov.kind == "hold":
        return _json_error(
            status.HTTP_202_ACCEPTED,
            {
                "status": "held",
                "receipt_id": str(receipt_id),
                "message": "Awaiting approval",
            },
            headers=hdr_receipt,
        )

    assert gov.allow is not None
    allow = gov.allow

    client: httpx.AsyncClient = _http_client_for(request)
    timeout = float(_settings.gateway_request_timeout_seconds)
    is_stream, _ = parse_stream_flag(body)

    hdrs = _headers_to_str_dict(request)
    out_headers, out_url, vault_key_id = await inject_credentials(
        db,
        api_ctx.project_id,
        api_ctx.created_by_user_id,
        classification.provider,
        hdrs,
        outbound_url,
        agent_id_header=agent_id,
    )
    _parsed_out = urlparse(out_url)
    logger.info(
        "gateway.upstream.request_prepared",
        project_id=str(api_ctx.project_id),
        provider=classification.provider,
        upstream_host=_parsed_out.hostname,
        upstream_path=_parsed_out.path,
        streaming=is_stream,
    )

    outbound_body = normalize_model_prefix(body, classification.provider)
    executed_at = datetime.now(UTC)

    if is_stream:

        async def stream_with_seal() -> AsyncIterator[bytes]:
            status_code = 502
            hasher = hashlib.sha256()
            started = time.monotonic()
            try:
                response, stream_bytes = await open_streaming_response(
                    client,
                    request.method,
                    out_url,
                    out_headers,
                    outbound_body,
                    timeout=timeout,
                )
                status_code = response.status_code
                async for chunk in stream_bytes:
                    hasher.update(chunk)
                    yield chunk
            except Exception as exc:
                logger.exception("gateway.stream_failed", receipt_id=str(allow.receipt_id))
                async with session_scope() as sdb:
                    await seal_after_transport_failure(
                        sdb,
                        receipt_id=allow.receipt_id,
                        project_id=api_ctx.project_id,
                        error_message=str(exc),
                    )
                return
            latency_ms = int((time.monotonic() - started) * 1000)
            outcome = {
                "target": classification.target,
                "action_type": classification.action_type,
                "risk": classification.risk,
                "http_status": status_code,
                "streaming": True,
                "upstream_audit": build_upstream_audit(
                    request_body=body,
                    response_body=None,
                    response_hash_hex=hasher.hexdigest(),
                    upstream_provider=classification.provider,
                    upstream_status=status_code,
                    upstream_latency_ms=latency_ms,
                    vault_key_id=vault_key_id,
                ),
            }
            async with session_scope() as sdb:
                await seal_after_success(
                    sdb,
                    receipt_id=allow.receipt_id,
                    project_id=api_ctx.project_id,
                    execution_data=outcome,
                    executed_at=executed_at,
                )

        out = sanitize_upstream_response_headers(httpx.Headers({}))
        return StreamingResponse(
            stream_with_seal(),
            media_type="text/event-stream",
            headers={**out, **hdr_receipt},
        )

    started = time.monotonic()
    try:
        upstream = await proxy_request(
            client,
            request.method,
            out_url,
            out_headers,
            outbound_body,
            timeout=timeout,
        )
        logger.info(
            "gateway.upstream.response",
            project_id=str(api_ctx.project_id),
            provider=classification.provider,
            status=upstream.status_code,
        )
    except httpx.TimeoutException:
        async with session_scope() as sdb:
            await seal_after_transport_failure(
                sdb,
                receipt_id=allow.receipt_id,
                project_id=api_ctx.project_id,
                error_message="upstream_timeout",
            )
        return _json_error(
            status.HTTP_504_GATEWAY_TIMEOUT,
            {"error": "upstream_timeout", "receipt_id": str(allow.receipt_id)},
            headers=hdr_receipt,
        )
    except Exception as exc:
        logger.exception("gateway.proxy_failed", receipt_id=str(allow.receipt_id))
        async with session_scope() as sdb:
            await seal_after_transport_failure(
                sdb,
                receipt_id=allow.receipt_id,
                project_id=api_ctx.project_id,
                error_message=str(exc),
            )
        return _json_error(
            status.HTTP_502_BAD_GATEWAY,
            {"error": "upstream_error", "receipt_id": str(allow.receipt_id)},
            headers=hdr_receipt,
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    outcome: dict[str, Any] = {
        "target": classification.target,
        "action_type": classification.action_type,
        "risk": classification.risk,
        "http_status": upstream.status_code,
        "streaming": False,
        "upstream_audit": build_upstream_audit(
            request_body=body,
            response_body=upstream.content,
            response_hash_hex=None,
            upstream_provider=classification.provider,
            upstream_status=upstream.status_code,
            upstream_latency_ms=latency_ms,
            vault_key_id=vault_key_id,
        ),
    }
    if upstream.status_code >= 400:
        outcome["provider_error_body_preview"] = _preview_upstream_error(upstream.content)
        logger.info(
            "gateway.proxy.upstream_error_body",
            status=upstream.status_code,
            body_preview=_preview_upstream_error(upstream.content),
        )
    async with session_scope() as sdb:
        await seal_after_success(
            sdb,
            receipt_id=allow.receipt_id,
            project_id=api_ctx.project_id,
            execution_data=outcome,
            executed_at=executed_at,
        )

    rh = sanitize_upstream_response_headers(upstream.headers)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={**rh, **hdr_receipt},
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from axiom.services.receipt.keys import get_signing_keys

    keys = get_signing_keys()
    logger.info("axiom.gateway.startup", evidence_key_id=keys.evidence_key_id[:16])
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        async with session_scope() as db:
            await load_governance_merkle_from_db(db)
        yield
    await close_redis()


app = FastAPI(
    title="AXIOM Governance Gateway",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _settings.environment != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _settings.environment != "production" else None,
)

app.add_middleware(BodySizeLimitMiddleware, max_bytes=_settings.gateway_max_body_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def _gateway_deps(
    request: Request,
    db: AsyncSession,
) -> tuple[APIKeyContext, bytes]:
    api_ctx = await authenticate_gateway_request(db, request)
    await check_gateway_rate_limit(api_ctx.project_id)
    try:
        body = await _read_body_limit(request, _settings.gateway_max_body_bytes)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "payload_too_large", "message": "Request body exceeds limit"},
        ) from None
    return api_ctx, body


def _governance_gate(gov: Any) -> tuple[dict[str, str], Response | None]:
    """Turn a governance outcome into the receipt header plus any short-circuit response.

    Returns ``(hdr_receipt, None)`` when the verdict is allow and the caller
    should proceed, or ``(hdr_receipt, response)`` for deny (403) and hold (202).
    """
    receipt_id = (
        gov.deny.receipt_id
        if gov.deny
        else gov.hold.receipt_id
        if gov.hold
        else gov.allow.receipt_id
        if gov.allow
        else None
    )
    assert receipt_id is not None
    hdr_receipt = {"X-Axiom-Receipt-Id": str(receipt_id)}
    if gov.kind == "deny":
        return hdr_receipt, _json_error(
            status.HTTP_403_FORBIDDEN,
            {"error": "governance_denied", "receipt_id": str(receipt_id)},
            headers=hdr_receipt,
        )
    if gov.kind == "hold":
        return hdr_receipt, _json_error(
            status.HTTP_202_ACCEPTED,
            {
                "status": "held",
                "receipt_id": str(receipt_id),
                "message": "Awaiting approval",
            },
            headers=hdr_receipt,
        )
    return hdr_receipt, None


async def _apply_named_vault_credential(
    db: AsyncSession,
    *,
    request: Request,
    api_ctx: APIKeyContext,
    receipt_id: UUID,
    out_headers: dict[str, str],
    hdr_receipt: dict[str, str],
) -> tuple[UUID | None, Response | None]:
    """Resolve the caller-named vault key and set Authorization on the outbound request.

    Credential injection for the generic proxy is opt-in and explicit: the caller
    names the key via ``X-Axiom-Vault-Key``. The target host is never used to
    infer which credential to use — host-based inference would let a request to
    an attacker-controlled URL select a credential the caller was not entitled
    to. With no header we inject nothing, which is the default and preserves the
    original fail-safe behaviour.

    Callers must invoke this only after the SSRF guard has accepted the target
    and governance has returned allow, so a blocked or denied request never
    causes a vault read.

    Returns ``(vault_key_id, None)`` on success (``vault_key_id`` is None when no
    header was supplied), or ``(None, response)`` when the named key does not
    resolve within the caller's own vault.
    """
    name = (request.headers.get("x-axiom-vault-key") or "").strip()
    if not name:
        return None, None

    resolved = await vault_service.get_key_and_id_by_name(db, api_ctx.created_by_user_id, name)
    if resolved is None:
        # Not found rather than forbidden: a key belonging to another tenant is
        # indistinguishable from one that does not exist, so the vault cannot be
        # enumerated through this endpoint.
        await seal_after_transport_failure(
            db,
            receipt_id=receipt_id,
            project_id=api_ctx.project_id,
            error_message="vault_key_not_found",
        )
        return None, _json_error(
            status.HTTP_404_NOT_FOUND,
            {
                "error": "vault_key_not_found",
                "message": "No active vault key with that name.",
                "receipt_id": str(receipt_id),
            },
            headers=hdr_receipt,
        )

    raw_key, vault_key_id = resolved
    out_headers["Authorization"] = f"Bearer {raw_key}"
    logger.info(
        "gateway.generic_proxy.credential_injected",
        project_id=str(api_ctx.project_id),
        vault_key_id=str(vault_key_id),
    )
    return vault_key_id, None


@app.api_route("/v1/proxy/{proxy_target:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def generic_proxy(
    proxy_target: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    api_ctx, body = await _gateway_deps(request, db)
    raw = unquote(proxy_target)
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw.lstrip("/")
    assert_public_http_url(raw)
    classification = GatewayClassification(
        action_type="tool.http.custom",
        target=raw,
        risk="medium",
        provider="custom",
    )
    agent_id = agent_id_from_headers(request.headers)
    gov = await run_gateway_governance(
        db,
        project_id=api_ctx.project_id,
        classification=classification,
        agent_id=agent_id,
    )
    hdr_receipt, gate_response = _governance_gate(gov)
    if gate_response is not None:
        return gate_response
    assert gov.allow is not None
    allow = gov.allow
    client: httpx.AsyncClient = _http_client_for(request)
    timeout = float(_settings.gateway_request_timeout_seconds)
    is_stream, _ = parse_stream_flag(body)
    hdrs = _headers_to_str_dict(request)
    out_headers = {k: v for k, v in hdrs.items() if not k.lower().startswith("x-axiom")}
    for drop in ("authorization", "Authorization"):
        out_headers.pop(drop, None)
    out_url = raw

    # Credential injection is opt-in and explicit; see the helper's docstring.
    # Reaching this point means the SSRF guard passed and governance allowed.
    vault_key_id, vault_error = await _apply_named_vault_credential(
        db,
        request=request,
        api_ctx=api_ctx,
        receipt_id=allow.receipt_id,
        out_headers=out_headers,
        hdr_receipt=hdr_receipt,
    )
    if vault_error is not None:
        return vault_error

    executed_at = datetime.now(UTC)
    if is_stream:

        async def stream_generic() -> AsyncIterator[bytes]:
            status_code = 502
            try:
                response, stream_bytes = await open_streaming_response(
                    client,
                    request.method,
                    out_url,
                    out_headers,
                    body,
                    timeout=timeout,
                )
                status_code = response.status_code
                async for chunk in stream_bytes:
                    yield chunk
            except Exception as exc:
                logger.exception("gateway.stream_failed", receipt_id=str(allow.receipt_id))
                async with session_scope() as sdb:
                    await seal_after_transport_failure(
                        sdb,
                        receipt_id=allow.receipt_id,
                        project_id=api_ctx.project_id,
                        error_message=str(exc),
                    )
                return
            outcome = {
                "target": classification.target,
                "action_type": classification.action_type,
                "risk": classification.risk,
                "http_status": status_code,
                "streaming": True,
                "vault_key_id": str(vault_key_id) if vault_key_id else None,
            }
            async with session_scope() as sdb:
                await seal_after_success(
                    sdb,
                    receipt_id=allow.receipt_id,
                    project_id=api_ctx.project_id,
                    execution_data=outcome,
                    executed_at=executed_at,
                )

        return StreamingResponse(
            stream_generic(),
            media_type="text/event-stream",
            headers={**hdr_receipt},
        )

    try:
        upstream = await proxy_request(
            client,
            request.method,
            out_url,
            out_headers,
            body,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        async with session_scope() as sdb:
            await seal_after_transport_failure(
                sdb,
                receipt_id=allow.receipt_id,
                project_id=api_ctx.project_id,
                error_message="upstream_timeout",
            )
        return _json_error(
            status.HTTP_504_GATEWAY_TIMEOUT,
            {"error": "upstream_timeout", "receipt_id": str(allow.receipt_id)},
            headers=hdr_receipt,
        )
    except Exception as exc:  # noqa: BLE001
        async with session_scope() as sdb:
            await seal_after_transport_failure(
                sdb,
                receipt_id=allow.receipt_id,
                project_id=api_ctx.project_id,
                error_message=str(exc),
            )
        return _json_error(
            status.HTTP_502_BAD_GATEWAY,
            {"error": "upstream_error", "receipt_id": str(allow.receipt_id)},
            headers=hdr_receipt,
        )

    outcome = {
        "target": classification.target,
        "action_type": classification.action_type,
        "risk": classification.risk,
        "http_status": upstream.status_code,
        "streaming": False,
        "vault_key_id": str(vault_key_id) if vault_key_id else None,
    }
    async with session_scope() as sdb:
        await seal_after_success(
            sdb,
            receipt_id=allow.receipt_id,
            project_id=api_ctx.project_id,
            execution_data=outcome,
            executed_at=executed_at,
        )
    rh = sanitize_upstream_response_headers(upstream.headers)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={**rh, **hdr_receipt},
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@app.post("/v1/{provider}/{path:path}")
async def gateway_llm_proxy(
    provider: str,
    path: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Universal LLM proxy for all registry providers.

    ``/v1/proxy/...`` is registered above so it takes precedence over this route.
    """
    api_ctx, body = await _gateway_deps(request, db)
    prov = provider.lower()
    logger.info(
        "gateway.llm_proxy.entered",
        project_id=str(api_ctx.project_id),
        provider=prov,
        path=path,
        body_bytes=len(body) if body else 0,
    )
    spec = get_provider_spec(prov)
    if spec is None:
        logger.warning(
            "gateway.llm_proxy.unknown_provider",
            project_id=str(api_ctx.project_id),
            provider=prov,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown_provider", "message": f"Unknown provider: {prov}"},
        )
    outbound_url = build_upstream_url(spec, path.strip("/"))
    logger.info(
        "gateway.dispatch",
        provider=prov,
        protocol=str(spec.protocol),
        outbound_url=outbound_url,
    )
    return await _run_governed_proxy(
        request=request,
        db=db,
        api_ctx=api_ctx,
        provider=prov,
        outbound_url=outbound_url,
        path_for_classify=path,
        body=body,
    )


