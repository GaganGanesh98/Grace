"""n8n escalation flow: outbound dispatch + HMAC signing + webhook client."""

from axiom.services.escalation.dispatcher import dispatch_escalation, schedule_escalation
from axiom.services.escalation.signing import SIGNATURE_HEADER, sign_body, verify_signature
from axiom.services.escalation.webhook_client import EscalationDeliveryError, post_with_retry

__all__ = [
    "SIGNATURE_HEADER",
    "EscalationDeliveryError",
    "dispatch_escalation",
    "post_with_retry",
    "schedule_escalation",
    "sign_body",
    "verify_signature",
]
