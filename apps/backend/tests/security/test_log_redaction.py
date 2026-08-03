from axiom.core.logging import redact_sensitive


def test_structlog_redacts_password_fields() -> None:
    event = {"msg": "signup", "password": "MySecret123", "email": "a@b.com"}
    out = redact_sensitive(None, None, event)
    assert out["password"] == "[REDACTED]"
    assert out["email"] == "a@b.com"
