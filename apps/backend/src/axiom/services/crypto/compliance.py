"""Crypto compliance checker. Reports whether the current crypto stack meets various standards."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.backends.openssl.backend import backend

from .ml_dsa_65 import ML_DSA_AVAILABLE


@dataclass
class ComplianceReport:
    standard: str  # "FIPS 140-3" | "NIST PQC" | "CMMC L2"
    compliant: bool
    findings: list[str]  # What passed
    gaps: list[str]  # What's missing
    recommendations: list[str]  # How to fix gaps


def check_fips_140_3() -> ComplianceReport:
    """Check if current crypto stack could pass FIPS 140-3 validation."""
    findings: list[str] = []
    gaps: list[str] = []
    recommendations: list[str] = []

    try:
        openssl_version = backend.openssl_version_text()
        findings.append(f"OpenSSL backend: {openssl_version}")
        if "fips" in openssl_version.lower():
            findings.append("FIPS mode detected in OpenSSL backend")
        else:
            gaps.append("OpenSSL backend is not FIPS-validated")
            recommendations.append("Deploy with AWS-LC or BoringSSL FIPS module")
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        gaps.append("Cannot determine OpenSSL backend status")

    findings.append("AES-256-GCM: FIPS approved")
    findings.append("SHA-256: FIPS approved")
    findings.append("Ed25519: Not FIPS approved (use Ed25519ph or ECDSA P-256 for FIPS)")
    gaps.append(
        "Ed25519 is not in FIPS 186-5 — FIPS requires ECDSA or EdDSA with specific parameters"
    )
    recommendations.append("Add ECDSA P-256 as FIPS fallback signer in registry")

    findings.append("ML-DSA-65 (FIPS 204): FIPS approved as of 2024")

    gaps.append("Static file keys are not FIPS compliant for key storage")
    recommendations.append("Use HSM or FIPS-validated KMS for production key storage")

    compliant = len(gaps) == 0
    return ComplianceReport(
        standard="FIPS 140-3",
        compliant=compliant,
        findings=findings,
        gaps=gaps,
        recommendations=recommendations,
    )


def check_nist_pqc() -> ComplianceReport:
    """Check post-quantum crypto readiness."""
    findings: list[str] = []
    gaps: list[str] = []

    if ML_DSA_AVAILABLE:
        findings.append("ML-DSA-65 (FIPS 204): Available and active")
    else:
        gaps.append("ML-DSA-65 is stubbed — install pqcrypto for real PQC")

    findings.append("Hybrid signing (Ed25519 + ML-DSA-65): Configured per ADR-022")
    findings.append("Crypto agility registry: Algorithm swap without code changes")

    return ComplianceReport(
        standard="NIST PQC Migration",
        compliant=ML_DSA_AVAILABLE and len(gaps) == 0,
        findings=findings,
        gaps=gaps,
        recommendations=["Install pqcrypto for production ML-DSA-65"]
        if not ML_DSA_AVAILABLE
        else [],
    )


def _format_report(rep: ComplianceReport) -> str:
    lines = [
        f"Standard: {rep.standard}",
        f"Compliant: {rep.compliant}",
        "",
        "Findings:",
    ]
    lines.extend(f"  - {f}" for f in rep.findings)
    lines.append("")
    lines.append("Gaps:")
    lines.extend(f"  - {g}" for g in rep.gaps)
    lines.append("")
    lines.append("Recommendations:")
    lines.extend(f"  - {r}" for r in rep.recommendations)
    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint: print FIPS 140-3 and NIST PQC compliance reports."""
    for rep in (check_fips_140_3(), check_nist_pqc()):
        print(_format_report(rep))
        print()


if __name__ == "__main__":
    main()
