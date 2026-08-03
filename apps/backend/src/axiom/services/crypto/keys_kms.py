"""AWS KMS / GCP KMS / HashiCorp Vault key provider. STUB — not implemented yet."""

from __future__ import annotations

from .keys import KeyMetadata, KeyProvider


class KMSKeyProvider(KeyProvider):
    """Production key provider backed by a FIPS-validated KMS or HSM.

    When implemented, each method will:
    - ``get_signing_key``: KMS Sign or unwrap data key for the ACTIVE key version.
    - ``get_verification_key``: fetch public key / cert for ``key_id`` from KMS or cert store.
    - ``rotate_key``: rotate key version, repoint alias, record reason in audit.
    - ``list_keys``: list versions via KMS ListKeys / DescribeKey style APIs.
    """

    async def get_signing_key(self, algorithm: str) -> tuple[bytes, KeyMetadata]:
        raise NotImplementedError(
            "KMS key provider requires configuration — see ADR-026",
        )

    async def get_verification_key(self, key_id: str) -> tuple[bytes, KeyMetadata]:
        raise NotImplementedError(
            "KMS key provider requires configuration — see ADR-026",
        )

    async def rotate_key(self, algorithm: str, reason: str) -> KeyMetadata:
        raise NotImplementedError(
            "KMS key provider requires configuration — see ADR-026",
        )

    async def list_keys(self, algorithm: str | None = None) -> list[KeyMetadata]:
        raise NotImplementedError(
            "KMS key provider requires configuration — see ADR-026",
        )
