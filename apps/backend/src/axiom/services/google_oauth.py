import secrets
import time
from typing import Any, cast
from urllib.parse import urlencode

import httpx
import structlog
from jose import JWTError, jwk, jwt

from axiom.config import get_settings
from axiom.core import errors
from axiom.services.redis_client import get_redis

logger = structlog.get_logger()

_jwks_cache: dict[str, Any] = {"expires": 0.0, "keys": []}


def _google_oauth_configuration_message() -> str:
    """Human-facing message listing missing env *names* only (never values)."""
    settings = get_settings()
    missing: list[str] = []
    if not (settings.google_client_id or "").strip():
        missing.append("GOOGLE_CLIENT_ID")
    secret = settings.google_client_secret.get_secret_value()
    if not (secret or "").strip():
        missing.append("GOOGLE_CLIENT_SECRET")
    names = ", ".join(missing)
    return (
        f"Google OAuth is not configured. Set non-empty environment variable(s): {names}. "
        "Ensure GOOGLE_REDIRECT_URI matches an authorized redirect URI in Google Cloud Console "
        f"(local dev default: http://localhost:3000/auth/callback/google). See docs/auth-setup.md."
    )


async def _fetch_google_jwks() -> list[dict[str, Any]]:
    now = time.time()
    if _jwks_cache["keys"] and now < float(_jwks_cache["expires"]):
        return cast(list[dict[str, Any]], _jwks_cache["keys"])
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/certs",
            timeout=15.0,
        )
    response.raise_for_status()
    body = response.json()
    keys = body.get("keys", [])
    if not isinstance(keys, list):
        msg = "Unexpected JWKS response from Google."
        raise errors.InvalidCredentialsError(msg)
    _jwks_cache["keys"] = keys
    _jwks_cache["expires"] = now + 3600.0
    return cast(list[dict[str, Any]], keys)


async def verify_google_id_token(
    id_token: str,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Validate Google's RS256 ID token.

    Google may include an ``at_hash`` claim; ``python-jose`` verifies it only when
    ``access_token`` is passed (same value returned with the ID token from the token
    endpoint). Callers that only have an ID token should pass ``access_token=None`` and
    rely on ``verify_at_hash=False`` for that decode (tests / rare paths).
    """
    settings = get_settings()
    try:
        headers = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        logger.error(
            "google_id_token_verify_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise errors.InvalidCredentialsError("Invalid Google identity token.") from exc
    kid = headers.get("kid")
    if not isinstance(kid, str) or not kid:
        raise errors.InvalidCredentialsError("Invalid Google identity token.")
    keys = await _fetch_google_jwks()
    jwk_dict = next((k for k in keys if k.get("kid") == kid), None)
    if not isinstance(jwk_dict, dict):
        raise errors.InvalidCredentialsError("Invalid Google identity token.")
    at = (access_token or "").strip()
    decode_options: dict[str, Any] = {
        "leeway": 120,
    }
    if not at:
        decode_options["verify_at_hash"] = False
    try:
        public_key = jwk.construct(jwk_dict)
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            access_token=at or None,
            options=decode_options,
        )
    except (JWTError, ValueError) as exc:
        logger.error(
            "google_id_token_verify_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise errors.InvalidCredentialsError("Invalid Google identity token.") from exc
    if not isinstance(claims, dict):
        raise errors.InvalidCredentialsError("Invalid Google identity token.")
    if claims.get("email_verified") is not True:
        raise errors.InvalidCredentialsError("Google email not verified.")
    return claims


async def build_authorize_url() -> tuple[str, str]:
    settings = get_settings()
    if (
        not (settings.google_client_id or "").strip()
        or not (settings.google_client_secret.get_secret_value() or "").strip()
    ):
        raise errors.OAuthConfigurationError(_google_oauth_configuration_message())
    state = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(f"oauth_state:{state}", "1", ex=600)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return url, state


async def exchange_code(*, code: str, state: str | None) -> dict[str, Any]:
    settings = get_settings()
    if (
        not (settings.google_client_id or "").strip()
        or not (settings.google_client_secret.get_secret_value() or "").strip()
    ):
        raise errors.OAuthConfigurationError(_google_oauth_configuration_message())
    if not state:
        raise errors.OAuthStateError("Invalid or expired OAuth state.")
    redis = get_redis()
    stored = await redis.get(f"oauth_state:{state}")
    if stored is None:
        raise errors.OAuthStateError("Invalid or expired OAuth state.")
    await redis.delete(f"oauth_state:{state}")

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
    if token_response.status_code != 200:
        raise errors.InvalidCredentialsError("Google token exchange failed.")
    token_payload: dict[str, Any] = token_response.json()
    id_token = str(token_payload.get("id_token", ""))
    if not id_token:
        raise errors.InvalidCredentialsError("Google token exchange failed.")
    access_raw = token_payload.get("access_token")
    access_for_verify = str(access_raw).strip() if access_raw else None
    claims = await verify_google_id_token(id_token, access_token=access_for_verify)
    email = str(claims.get("email", ""))
    sub = str(claims.get("sub", ""))
    if not sub or not email:
        raise errors.InvalidCredentialsError("Google profile missing required fields.")
    return {
        "sub": sub,
        "email": email,
        "name": claims.get("name"),
        "picture": claims.get("picture"),
    }
