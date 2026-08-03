import pytest

from axiom.core.security import UnsafeUrlError, validate_external_url


@pytest.mark.security
def test_ssrf_helper_blocks_loopback_literal() -> None:
    with pytest.raises(UnsafeUrlError):
        validate_external_url("https://127.0.0.2/nope")
