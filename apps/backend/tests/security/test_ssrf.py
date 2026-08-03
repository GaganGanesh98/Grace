import pytest

from axiom.core.security import UnsafeUrlError, validate_external_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/foo",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.20.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
@pytest.mark.security
def test_validate_external_url_blocks_private_ranges(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_external_url(url)


@pytest.mark.security
def test_validate_external_url_allows_public_hostname() -> None:
    assert validate_external_url("https://example.com/path").startswith("https://")
