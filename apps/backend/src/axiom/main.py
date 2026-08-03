import asyncio
import logging as pylogging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, Request, WebSocket, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from axiom.config import get_settings
from axiom.core import errors as domain_errors
from axiom.core.logging import configure_structlog
from axiom.db import session_scope
from axiom.middleware.body_size import BodySizeLimitMiddleware
from axiom.middleware.correlation import CorrelationIDMiddleware
from axiom.middleware.logging import RequestLoggingMiddleware
from axiom.middleware.rate_limit import limiter
from axiom.middleware.security_headers import SecurityHeadersMiddleware
from axiom.routers import (
    agents,
    api_keys,
    auth,
    disclose,
    govern,
    health,
    members,
    policies,
    preflight,
    projects,
    users,
    vault,
    verify,
    webhooks,
)
from axiom.routers.v1 import agent_definitions as agent_definitions_router
from axiom.routers.v1 import agent_runs as agent_runs_router
from axiom.routers.v1 import approvals as approvals_router
from axiom.routers.v1 import chains as chains_router
from axiom.routers.v1 import command_center as command_center_router
from axiom.routers.v1 import events as v1_events
from axiom.routers.v1 import governance as governance_engine
from axiom.schemas.common import ErrorBody, ErrorEnvelope
from axiom.services.events import schedule_approval_resolved, schedule_receipt_sealed
from axiom.services.governance.approval_expire import expire_due_hold_receipts
from axiom.services.governance.receipt import load_governance_merkle_from_db
from axiom.services.redis_client import close_redis
from axiom.workers.websocket import handle_run_stream

logger = structlog.get_logger()
settings = get_settings()


async def _approval_expiry_background_loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            async with session_scope() as db:
                batch = await expire_due_hold_receipts(db)
            for receipt, intent, _project_id, verdict_str in batch:
                schedule_approval_resolved(
                    receipt.project_id, receipt_id=receipt.id, resolution="expired"
                )
                schedule_receipt_sealed(
                    receipt.project_id,
                    receipt_id=receipt.id,
                    verdict_raw=verdict_str,
                    agent_id=str(intent.agent_id),
                )
        except Exception:
            logger.exception("governance.approval_expire.background_failed")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_structlog(log_level=settings.log_level, environment=settings.environment)
    from axiom.services.receipt.keys import get_signing_keys

    keys = get_signing_keys()
    logger.info(
        "axiom.startup",
        environment=settings.environment,
        evidence_key_id=keys.evidence_key_id[:16],
    )
    async with session_scope() as db:
        await load_governance_merkle_from_db(db)
    _app.state.approval_expiry_task = asyncio.create_task(_approval_expiry_background_loop())
    yield
    await close_redis()
    logger.info("axiom.shutdown")


app = FastAPI(
    title="AXIOM API",
    version="0.1.0",
    description="Cryptographic governance proof layer for AI agents.",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    default_response_class=JSONResponse,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(members.router, prefix="/api/v1/projects", tags=["members"])
app.include_router(agents.router, prefix="/api/v1/projects", tags=["agents"])
app.include_router(policies.router, prefix="/api/v1/projects", tags=["policies"])
app.include_router(api_keys.router, prefix="/api/v1/projects", tags=["api_keys"])
app.include_router(vault.router, prefix="/api/v1/vault", tags=["vault"])
app.include_router(govern.router, prefix="/v1", tags=["govern"])
app.include_router(approvals_router.router, prefix="/v1/governance", tags=["governance-approvals"])
app.include_router(governance_engine.router, prefix="/v1/governance", tags=["governance-engine"])
app.include_router(chains_router.router, prefix="/v1/chains", tags=["governance-chains"])
app.include_router(preflight.router, prefix="/v1", tags=["preflight"])
app.include_router(verify.router, prefix="/v1", tags=["verify"])
app.include_router(disclose.router, prefix="/v1", tags=["disclose"])
app.include_router(agent_definitions_router.router, prefix="/v1", tags=["agent-definitions"])
app.include_router(agent_runs_router.router, prefix="/v1", tags=["agent-runs"])
app.include_router(command_center_router.router, prefix="/v1", tags=["command-center"])
app.include_router(v1_events.router, prefix="/v1", tags=["events"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


@app.websocket("/ws/agent-runs/{run_id}")
async def websocket_agent_run(websocket: WebSocket, run_id: UUID) -> None:
    token = websocket.query_params.get("token")
    await handle_run_stream(websocket, run_id, token)


@app.exception_handler(RequestValidationError)
async def validation_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": {"field_errors": exc.errors()},
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    pylogging.getLogger("axiom").exception("unhandled.exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred. Please try again or contact support.",
            },
        },
    )


def _domain_to_http(exc: domain_errors.DomainError) -> tuple[int, str]:
    if isinstance(exc, domain_errors.PermissionDeniedError):
        return status.HTTP_403_FORBIDDEN, "forbidden"
    if isinstance(exc, domain_errors.UserNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.ProjectNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.MemberNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.AgentNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.PolicyNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.ApiKeyNotFoundError):
        return status.HTTP_404_NOT_FOUND, "not_found"
    if isinstance(exc, domain_errors.InvalidCredentialsError):
        return status.HTTP_401_UNAUTHORIZED, "unauthorized"
    if isinstance(exc, domain_errors.InvalidTokenError):
        return status.HTTP_401_UNAUTHORIZED, "unauthorized"
    if isinstance(exc, domain_errors.RefreshTokenRevokedError):
        return status.HTTP_401_UNAUTHORIZED, "unauthorized"
    if isinstance(exc, domain_errors.InactiveUserError):
        return status.HTTP_403_FORBIDDEN, "forbidden"
    if isinstance(exc, domain_errors.DuplicateEmailError):
        return status.HTTP_409_CONFLICT, "conflict"
    if isinstance(exc, domain_errors.DuplicateSlugError):
        return status.HTTP_409_CONFLICT, "conflict"
    if isinstance(exc, domain_errors.ConflictError):
        return status.HTTP_409_CONFLICT, "conflict"
    if isinstance(exc, domain_errors.ValidationError):
        return status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error"
    if isinstance(exc, domain_errors.WeakPasswordError):
        return status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error"
    if isinstance(exc, domain_errors.OAuthStateError):
        return status.HTTP_400_BAD_REQUEST, "bad_request"
    if isinstance(exc, domain_errors.OAuthConfigurationError):
        return status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable"
    if isinstance(exc, domain_errors.AccountLockedError):
        return status.HTTP_429_TOO_MANY_REQUESTS, "account_locked"
    return status.HTTP_400_BAD_REQUEST, "bad_request"


@app.exception_handler(domain_errors.DomainError)
async def domain_error_handler(_request: Request, exc: domain_errors.DomainError) -> JSONResponse:
    if isinstance(exc, domain_errors.VaultKeyInUseError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "vault_key_in_use",
                    "message": str(exc),
                    "details": {
                        "referencing_agents": [
                            {"id": str(aid), "name": name}
                            for aid, name in exc.referencing_agents
                        ],
                    },
                },
            },
        )
    status_code, code = _domain_to_http(exc)
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=str(exc), details={"field_errors": []}),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())
