from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from axiom.config import get_settings

_settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.redis_url,
    default_limits=["60/minute"],
)


def api_key_limit_key(request: Request) -> str:
    """Rate-limit bucket keyed on the presented API key (fallback to IP).

    We read from the Authorization header or X-Api-Key header. Falling back
    to IP means anonymous / unauthenticated probes still get a bucket rather
    than an unbounded one.
    """

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return f"apikey:{token[:32]}"
    header_key = request.headers.get("x-api-key", "").strip()
    if header_key:
        return f"apikey:{header_key[:32]}"
    return f"ip:{get_remote_address(request)}"
