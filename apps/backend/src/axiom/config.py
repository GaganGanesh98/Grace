import json
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

    environment: str = "development"
    app_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("AXIOM_FRONTEND_URL", "APP_URL"),
    )
    api_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("AXIOM_API_URL", "API_URL"),
    )
    log_level: str = "INFO"

    database_url: str
    database_echo: bool = False

    redis_url: str

    secret_key: SecretStr
    jwt_secret: SecretStr
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"
    encryption_key: SecretStr

    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback/google",
        validation_alias=AliasChoices("GOOGLE_REDIRECT_URI", "AXIOM_GOOGLE_REDIRECT_URI"),
    )

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("AXIOM_CORS_ORIGINS", "BACKEND_CORS_ORIGINS"),
    )

    # Documented for production / future use (session cookies are set by the Next.js BFF today).
    axiom_cookie_secure: bool = Field(default=False, validation_alias=AliasChoices("AXIOM_COOKIE_SECURE"))
    axiom_cookie_samesite: str = Field(default="lax", validation_alias=AliasChoices("AXIOM_COOKIE_SAMESITE"))
    axiom_cookie_domain: str = Field(default="", validation_alias=AliasChoices("AXIOM_COOKIE_DOMAIN"))

    # --- Phase 2 governance-engine signing + evidence keys ---
    # Single AXIOM-wide keys for Phase 2. Per-project keys land in Phase 2.5.
    # All are optional: in development/test they auto-generate with a loud
    # warning on first startup; in production a missing value refuses startup.
    axiom_ed25519_private_pem: SecretStr | None = None
    axiom_ed25519_public_pem: str | None = None
    axiom_ml_dsa_private_b64: SecretStr | None = None
    axiom_ml_dsa_public_b64: str | None = None
    axiom_evidence_key_b64: SecretStr | None = None

    verify_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("AXIOM_VERIFY_BASE_URL", "VERIFY_BASE_URL"),
    )

    # Pre-flight prediction cache (Phase 2.25)
    preflight_cache_ttl_seconds: int = 3600

    # Governance gateway (port 8001) — vault uses same key material as AXIOM_EVIDENCE_KEY_B64
    gateway_port: int = Field(default=8001, validation_alias=AliasChoices("AXIOM_GATEWAY_PORT", "GATEWAY_PORT"))
    gateway_rate_limit_per_minute: int = Field(
        default=200,
        validation_alias=AliasChoices("AXIOM_GATEWAY_RATE_LIMIT_PER_MINUTE", "GATEWAY_RATE_LIMIT_PER_MINUTE"),
    )
    gateway_request_timeout_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("AXIOM_GATEWAY_REQUEST_TIMEOUT_SECONDS", "GATEWAY_REQUEST_TIMEOUT_SECONDS"),
    )
    gateway_max_body_bytes: int = Field(
        default=10_485_760,
        validation_alias=AliasChoices("AXIOM_GATEWAY_MAX_BODY_BYTES", "GATEWAY_MAX_BODY_BYTES"),
    )
    gateway_enabled: bool = Field(default=True, validation_alias=AliasChoices("AXIOM_GATEWAY_ENABLED", "GATEWAY_ENABLED"))

    # Plaintext project API key for the agent worker → governance gateway (localhost).
    worker_gateway_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AXIOM_WORKER_GATEWAY_API_KEY",
            "WORKER_GATEWAY_API_KEY",
        ),
    )

    # Optional Tavily key for agent worker web search (can also be supplied via project vault).
    tavily_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("TAVILY_API_KEY"))

    # Key rotation notice for Command Center (ISO-8601 date YYYY-MM-DD; optional).
    axiom_key_rotation_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AXIOM_KEY_ROTATION_DATE"),
    )
    # Optional TSA base URL for Command Center status (e.g. RFC 3161 endpoint); unset → null in API.
    axiom_tsa_authority_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AXIOM_TSA_AUTHORITY_URL", "AXIOM_TSA_URL"),
    )
    # Phase 7.6 — project SSE; override to e.g. 2 in tests
    events_heartbeat_interval_seconds: float = Field(
        default=20.0,
        validation_alias=AliasChoices("AXIOM_EVENTS_HEARTBEAT_SECONDS", "EVENTS_HEARTBEAT_INTERVAL_SECONDS"),
    )

    # --- Semantic policy matching (pgvector) ---
    # Default provider is fastembed (local, free, no key). Set provider=openai to
    # use OpenAI text-embedding-3-small via httpx (dimensions pinned to 384 so the
    # pgvector column never changes). `embedding_model` names the model for the
    # active provider (a fastembed model id, or an OpenAI model name).
    embedding_provider: str = Field(
        default="fastembed",
        validation_alias=AliasChoices("AXIOM_EMBEDDING_PROVIDER"),
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        validation_alias=AliasChoices("AXIOM_EMBEDDING_MODEL"),
    )
    embedding_openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AXIOM_EMBEDDING_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    embedding_openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("AXIOM_EMBEDDING_OPENAI_BASE_URL"),
    )

    # --- n8n escalation flow ---
    # When an action is held/escalated (pending approval), POST a structured
    # payload to N8N_ESCALATION_WEBHOOK_URL. n8n calls back to resolve it; the
    # callback is HMAC-verified with N8N_CALLBACK_SECRET. Off by default so
    # nothing fires unless configured.
    escalation_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("ESCALATION_ENABLED"),
    )
    n8n_escalation_webhook_url: str = Field(
        default="",
        validation_alias=AliasChoices("N8N_ESCALATION_WEBHOOK_URL"),
    )
    n8n_callback_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("N8N_CALLBACK_SECRET"),
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
