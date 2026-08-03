from axiom.core.security import compare_digest_str


def test_compare_digest_str_mismatched_lengths_safe() -> None:
    assert compare_digest_str("a", "bb") is False


def test_compare_digest_str_equal_strings() -> None:
    assert compare_digest_str("same-id", "same-id") is True
