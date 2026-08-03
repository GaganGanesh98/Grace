"""Public exceptions for the AXIOM Python SDK."""


class AxiomError(Exception):
    """Base exception for all AXIOM SDK errors."""

    pass


class AuthError(AxiomError):
    """API key is invalid or revoked."""

    pass


class GovernanceDenied(AxiomError):
    """Action was denied by governance policy. Only raised when enforce=True."""

    def __init__(self, verdict: str, reason: str | None, receipt_id: str) -> None:
        self.verdict = verdict
        self.reason = reason
        self.receipt_id = receipt_id
        super().__init__(
            f"Governance denied: {reason or 'no reason provided'} "
            f"(verdict={verdict}, receipt_id={receipt_id})"
        )


class GovernanceHeld(AxiomError):
    """Action was held for human approval. Only raised when enforce=True."""

    def __init__(self, receipt_id: str) -> None:
        self.receipt_id = receipt_id
        super().__init__(
            f"Governance held: awaiting human approval (receipt_id={receipt_id})"
        )
