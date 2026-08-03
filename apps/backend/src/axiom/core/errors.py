from __future__ import annotations

from uuid import UUID


class DomainError(Exception):
    """Base class for expected domain failures."""


class UserNotFoundError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class DuplicateEmailError(DomainError):
    pass


class DuplicateSlugError(DomainError):
    pass


class PermissionDeniedError(DomainError):
    pass


class ProjectNotFoundError(DomainError):
    pass


class MemberNotFoundError(DomainError):
    pass


class AgentNotFoundError(DomainError):
    pass


class PolicyNotFoundError(DomainError):
    pass


class ApiKeyNotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class InvalidTokenError(DomainError):
    pass


class RefreshTokenRevokedError(DomainError):
    pass


class OAuthStateError(DomainError):
    pass


class OAuthConfigurationError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class VaultKeyInUseError(DomainError):
    """Deleting a vault key blocked because agent_definitions reference it."""

    def __init__(
        self,
        referencing_agents: list[tuple[UUID, str]],
        message: str | None = None,
    ) -> None:
        self.referencing_agents: list[tuple[UUID, str]] = referencing_agents
        if message is not None:
            super().__init__(message)
            return
        id_list = ", ".join(str(aid) for aid, _ in referencing_agents)
        super().__init__(f"Cannot delete: in use by agents [{id_list}].")


class WeakPasswordError(DomainError):
    pass


class InactiveUserError(DomainError):
    pass


class AccountLockedError(DomainError):
    pass


class DecryptionError(DomainError):
    """Raised when authenticated decryption fails (for example, wrong key or tampering)."""
