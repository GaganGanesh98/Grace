"""Unit tests for compliance reporting."""

from __future__ import annotations

from axiom.services.crypto.compliance import check_fips_140_3, check_nist_pqc


def test_fips_report_structure() -> None:
    rep = check_fips_140_3()
    assert rep.standard == "FIPS 140-3"
    assert isinstance(rep.findings, list)
    assert isinstance(rep.gaps, list)
    assert rep.compliant is False


def test_nist_pqc_report() -> None:
    rep = check_nist_pqc()
    assert rep.standard == "NIST PQC Migration"
    assert len(rep.findings) >= 1
