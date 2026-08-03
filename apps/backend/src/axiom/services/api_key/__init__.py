"""API-key verification for the public governance endpoints.

Distinct from ``services.api_keys`` (management CRUD for the web UI): this
module VERIFIES a presented key at request time, returning an
``APIKeyContext`` that binds a call to its project and agent. Constant-time
comparison, revocation check, expiry check, and minimum-scope check all
live here.
"""

from axiom.services.api_key.service import (
    APIKeyContext,
    APIKeyVerificationError,
    verify_key,
)

__all__ = ["APIKeyContext", "APIKeyVerificationError", "verify_key"]
