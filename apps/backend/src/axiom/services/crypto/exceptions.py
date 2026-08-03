"""Typed error hierarchy for crypto operations. Never leak raw library exceptions."""


class CryptoError(Exception):
    """Base exception for all crypto operations."""


class CryptoInputError(CryptoError):
    """Invalid input to a crypto function (wrong type, length, format)."""


class SignatureError(CryptoError):
    """Signature creation or verification failed."""


class VerificationError(CryptoError):
    """Proof or receipt verification failed."""


class DecryptionError(CryptoError):
    """Decryption failed (wrong key, tampered ciphertext, invalid nonce)."""


class KeyError_(CryptoError):  # noqa: N801, N818
    """Key generation, loading, or validation failed. Named KeyError_ to avoid shadowing builtin."""


class AlgorithmNotFoundError(CryptoError):
    """Requested algorithm is not registered."""


class NonceReuseError(CryptoError):
    """AES-GCM nonce was reused with the same key. Catastrophic — abort immediately."""
