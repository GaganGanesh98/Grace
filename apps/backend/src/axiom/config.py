import json
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/backend/src/axiom/config.py → parents[4] == repository root
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[4]


def _env_files() -> tuple[Path, ...]:
    """Load order: earlier files first; later files override duplicate keys.

    Typical layout: repo ``.env`` / ``.env.dev`` for shared defaults, then
    ``apps/backend/.env`` (gitignored) for machine-local backend secrets.
    """

    return (
        REPO_ROOT / ".env",
        REPO_ROOT / ".env.dev",
        REPO_ROOT / "apps" / "backend" / ".env",
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(  # type: ignore[typeddict-unknown-key]
        env_file=_env_files(),
        env_file_encoding="utf-8",
        env_ignore_missing=True,
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("GRACE_ENVIRONMENT", "ENVIRONMENT"),
    )
    app_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("GRACE_FRONTEND_URL", "AXIOM_FRONTEND_URL", "APP_URL"),
    )
    api_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("GRACE_API_URL", "AXIOM_API_URL", "API_URL"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("GRACE_LOG_LEVEL", "LOG_LEVEL"),
    )

    database_url: str = Field(
        validation_alias=AliasChoices("GRACE_DATABASE_URL", "DATABASE_URL"),
    )
    database_echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("GRACE_DATABASE_ECHO", "DATABASE_ECHO"),
    )

    redis_url: str = Field(
        validation_alias=AliasChoices("GRACE_REDIS_URL", "REDIS_URL"),
    )

    secret_key: SecretStr = Field(
        validation_alias=AliasChoices("GRACE_SECRET_KEY", "SECRET_KEY"),
    )
    jwt_secret: SecretStr = Field(
        validation_alias=AliasChoices("GRACE_JWT_SECRET", "JWT_SECRET"),
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices(
            "GRACE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
        ),
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "GRACE_JWT_REFRESH_TOKEN_EXPIRE_DAYS", "JWT_REFRESH_TOKEN_EXPIRE_DAYS"
        ),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("GRACE_JWT_ALGORITHM", "JWT_ALGORITHM"),
    )
    encryption_key: SecretStr = Field(
        validation_alias=AliasChoices("GRACE_ENCRYPTION_KEY", "ENCRYPTION_KEY"),
    )

    google_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GRACE_GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID"),
    )
    google_client_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GRACE_GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"),
    )
    google_redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback/google",
        validation_alias=AliasChoices(
            "GRACE_GOOGLE_REDIRECT_URI", "GOOGLE_REDIRECT_URI", "AXIOM_GOOGLE_REDIRECT_URI"
        ),
    )

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices(
            "GRACE_CORS_ORIGINS", "AXIOM_CORS_ORIGINS", "BACKEND_CORS_ORIGINS"
        ),
    )

    # Documented for production / future use (session cookies are set by the Next.js BFF today).
    axiom_cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("GRACE_COOKIE_SECURE", "AXIOM_COOKIE_SECURE"),
    )
    axiom_cookie_samesite: str = Field(
        default="lax",
        validation_alias=AliasChoices("GRACE_COOKIE_SAMESITE", "AXIOM_COOKIE_SAMESITE"),
    )
    axiom_cookie_domain: str = Field(
        default="",
        validation_alias=AliasChoices("GRACE_COOKIE_DOMAIN", "AXIOM_COOKIE_DOMAIN"),
    )

    # --- Phase 2 governance-engine signing + evidence keys ---
    # Single AXIOM-wide keys for Phase 2. Per-project keys land in Phase 2.5.
    # All are optional: in development/test they auto-generate with a loud
    # warning on first startup; in production a missing value refuses startup.
    axiom_ed25519_private_pem: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_ED25519_PRIVATE_PEM", "AXIOM_ED25519_PRIVATE_PEM"),
    )
    axiom_ed25519_public_pem: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_ED25519_PUBLIC_PEM", "AXIOM_ED25519_PUBLIC_PEM"),
    )
    axiom_ml_dsa_private_b64: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_ML_DSA_PRIVATE_B64", "AXIOM_ML_DSA_PRIVATE_B64"),
    )
    axiom_ml_dsa_public_b64: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_ML_DSA_PUBLIC_B64", "AXIOM_ML_DSA_PUBLIC_B64"),
    )
    axiom_evidence_key_b64: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_EVIDENCE_KEY_B64", "AXIOM_EVIDENCE_KEY_B64"),
    )

    # --- Phase 8.2 vault key-encryption key (envelope encryption) ---
    # GRACE_* only: these are new, they have no AXIOM_* legacy spelling, and
    # must not acquire one. When the KEK is unset it is derived from the
    # evidence key by HKDF (see services/crypto/kek_registry.py) so local dev
    # needs no new configuration; production sets it explicitly for full
    # separation. GRACE_VAULT_KEK_PREVIOUS_B64 is a comma-separated list of
    # retired KEKs that must stay readable until their row count reaches zero.
    grace_vault_kek_b64: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_VAULT_KEK_B64"),
    )
    grace_vault_kek_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_VAULT_KEK_ID"),
    )
    grace_vault_kek_previous_b64: str = Field(
        default="",
        validation_alias=AliasChoices("GRACE_VAULT_KEK_PREVIOUS_B64"),
    )

    verify_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices(
            "GRACE_VERIFY_BASE_URL", "AXIOM_VERIFY_BASE_URL", "VERIFY_BASE_URL"
        ),
    )

    # Pre-flight prediction cache (Phase 2.25)
    preflight_cache_ttl_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices(
            "GRACE_PREFLIGHT_CACHE_TTL_SECONDS", "PREFLIGHT_CACHE_TTL_SECONDS"
        ),
    )

    # Governance gateway (port 8001). Since Phase 8.2 the vault it reads uses its
    # own KEK (GRACE_VAULT_KEK_B64), not the evidence key.
    gateway_port: int = Field(
        default=8001,
        validation_alias=AliasChoices("GRACE_GATEWAY_PORT", "AXIOM_GATEWAY_PORT", "GATEWAY_PORT"),
    )
    gateway_rate_limit_per_minute: int = Field(
        default=200,
        validation_alias=AliasChoices(
            "GRACE_GATEWAY_RATE_LIMIT_PER_MINUTE",
            "AXIOM_GATEWAY_RATE_LIMIT_PER_MINUTE",
            "GATEWAY_RATE_LIMIT_PER_MINUTE",
        ),
    )
    gateway_request_timeout_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices(
            "GRACE_GATEWAY_REQUEST_TIMEOUT_SECONDS",
            "AXIOM_GATEWAY_REQUEST_TIMEOUT_SECONDS",
            "GATEWAY_REQUEST_TIMEOUT_SECONDS",
        ),
    )
    gateway_max_body_bytes: int = Field(
        default=10_485_760,
        validation_alias=AliasChoices(
            "GRACE_GATEWAY_MAX_BODY_BYTES",
            "AXIOM_GATEWAY_MAX_BODY_BYTES",
            "GATEWAY_MAX_BODY_BYTES",
        ),
    )
    gateway_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "GRACE_GATEWAY_ENABLED", "AXIOM_GATEWAY_ENABLED", "GATEWAY_ENABLED"
        ),
    )

    # MCP governance server (Phase 7.0). Mounted at /mcp on the main API.
    # Tools require API keys scoped 'mcp:read' / 'mcp:write'.
    mcp_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("GRACE_MCP_ENABLED", "AXIOM_MCP_ENABLED", "MCP_ENABLED"),
    )

    # Plaintext project API key for the agent worker → governance gateway (localhost).
    worker_gateway_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GRACE_WORKER_GATEWAY_API_KEY",
            "AXIOM_WORKER_GATEWAY_API_KEY",
            "WORKER_GATEWAY_API_KEY",
        ),
    )

    # Optional Tavily key for agent worker web search (can also be supplied via project vault).
    tavily_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_TAVILY_API_KEY", "TAVILY_API_KEY"),
    )

    # Key rotation notice for Command Center (ISO-8601 date YYYY-MM-DD; optional).
    axiom_key_rotation_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_KEY_ROTATION_DATE", "AXIOM_KEY_ROTATION_DATE"),
    )
    # Optional TSA base URL for Command Center status (e.g. RFC 3161 endpoint); unset → null in API.
    axiom_tsa_authority_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GRACE_TSA_AUTHORITY_URL", "AXIOM_TSA_AUTHORITY_URL", "AXIOM_TSA_URL"
        ),
    )
    # Phase 7.6 — project SSE; override to e.g. 2 in tests
    events_heartbeat_interval_seconds: float = Field(
        default=20.0,
        validation_alias=AliasChoices(
            "GRACE_EVENTS_HEARTBEAT_SECONDS",
            "AXIOM_EVENTS_HEARTBEAT_SECONDS",
            "EVENTS_HEARTBEAT_INTERVAL_SECONDS",
        ),
    )

    # --- Semantic policy matching (pgvector) ---
    # Default provider is fastembed (local, free, no key). Set provider=openai to
    # use OpenAI text-embedding-3-small via httpx (dimensions pinned to 384 so the
    # pgvector column never changes). `embedding_model` names the model for the
    # active provider (a fastembed model id, or an OpenAI model name).
    embedding_provider: str = Field(
        default="fastembed",
        validation_alias=AliasChoices("GRACE_EMBEDDING_PROVIDER", "AXIOM_EMBEDDING_PROVIDER"),
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        validation_alias=AliasChoices("GRACE_EMBEDDING_MODEL", "AXIOM_EMBEDDING_MODEL"),
    )
    embedding_openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GRACE_EMBEDDING_OPENAI_API_KEY",
            "AXIOM_EMBEDDING_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ),
    )
    embedding_openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices(
            "GRACE_EMBEDDING_OPENAI_BASE_URL", "AXIOM_EMBEDDING_OPENAI_BASE_URL"
        ),
    )

    # --- n8n escalation flow ---
    # When an action is held/escalated (pending approval), POST a structured
    # payload to N8N_ESCALATION_WEBHOOK_URL. n8n calls back to resolve it; the
    # callback is HMAC-verified with N8N_CALLBACK_SECRET. Off by default so
    # nothing fires unless configured.
    escalation_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("GRACE_ESCALATION_ENABLED", "ESCALATION_ENABLED"),
    )
    n8n_escalation_webhook_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GRACE_N8N_ESCALATION_WEBHOOK_URL", "N8N_ESCALATION_WEBHOOK_URL"
        ),
    )
    n8n_callback_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GRACE_N8N_CALLBACK_SECRET", "N8N_CALLBACK_SECRET"),
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return []
            if s.startswith("["):
                parsed: object = json.loads(s)
                if not isinstance(parsed, list):
                    msg = "AXIOM_CORS_ORIGINS JSON must be an array"
                    raise ValueError(msg)
                return [str(item) for item in parsed]
            return [part.strip() for part in s.split(",") if part.strip()]
        msg = "Invalid CORS origins value"
        raise TypeError(msg)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _grace_aliases() -> dict[str, str]:
    """``AXIOM_X`` → the ``GRACE_X`` that supersedes it, from the field aliases."""
    out: dict[str, str] = {}
    for field in Settings.model_fields.values():
        alias = field.validation_alias
        names = list(getattr(alias, "choices", []) or [])
        grace = next((n for n in names if isinstance(n, str) and n.startswith("GRACE_")), None)
        if grace is None:
            continue
        for name in names:
            if isinstance(name, str) and name.startswith("AXIOM_"):
                out[name] = grace
    return out


def deprecated_env_vars(environ: Mapping[str, str] | None = None) -> list[tuple[str, str]]:
    """``AXIOM_*`` variables still set, paired with their ``GRACE_*`` replacement.

    ADR-029 deferred this rename; Phase 8.2 executes it behind aliases. The list
    is logged at startup so the eventual removal of the ``AXIOM_*`` spelling is a
    checklist rather than an archaeology exercise.
    """
    env = os.environ if environ is None else environ
    return sorted((old, new) for old, new in _grace_aliases().items() if old in env)
