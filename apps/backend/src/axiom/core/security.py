import hmac
import ipaddress
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from axiom.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

_dummy_hash: str | None = None


def _timing_safe_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _pwd_context.hash("axiom-timing-mitigation-dummy-secret")
    return _dummy_hash


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def verify_password_or_dummy(plain: str, hashed: str | None) -> bool:
    """Verify password; use dummy hash when user has no password row."""
    effective = hashed if hashed is not None else _timing_safe_dummy_hash()
    return _pwd_context.verify(plain, effective)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "refresh",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


class UnsafeUrlError(ValueError):
    """Raised when a URL is rejected by the SSRF guard."""


BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
]

ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_external_url(url: str) -> str:
    """
    Validate that a URL is safe for the server to fetch.
    Rejects: non-http(s) schemes, private IPs, link-local, loopback, metadata services.
    Returns the validated URL.
    Raises UnsafeUrlError on rejection.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        msg = f"Scheme {parsed.scheme!r} not allowed"
        raise UnsafeUrlError(msg)
    if not parsed.hostname:
        msg = "URL has no hostname"
        raise UnsafeUrlError(msg)
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return url
    for net in BLOCKED_NETWORKS:
        if ip in net:
            msg = f"IP {ip} is in blocked network {net}"
            raise UnsafeUrlError(msg)
    return url


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        msg = f"Invalid token: {exc}"
        raise ValueError(msg) from exc
    alg = header.get("alg")
    if alg is None or str(alg).lower() == "none":
        msg = "Invalid token algorithm"
        raise ValueError(msg)
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        msg = f"Invalid token: {exc}"
        raise ValueError(msg) from exc


def compare_digest_str(a: str, b: str) -> bool:
    """Constant-time comparison for ASCII-safe strings (e.g. Redis-stored ids)."""
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except (TypeError, ValueError):
        return False
