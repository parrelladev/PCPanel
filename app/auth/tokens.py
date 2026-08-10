"""Generation and verification of opaque Auth domain secrets."""

from __future__ import annotations

import hashlib
import hmac
import secrets


DEVICE_TOKEN_BYTES = 32
PAIRING_CODE_DIGITS = 6


class TokenService:
    """Stateless cryptographic operations for tokens and pairing codes."""

    __slots__ = ()

    @staticmethod
    def generate_device_token() -> str:
        """Return an opaque bearer token backed by 256 random bits."""
        return secrets.token_urlsafe(DEVICE_TOKEN_BYTES)

    @staticmethod
    def hash_device_token(token: str) -> str:
        return TokenService._hash_secret(token)

    @staticmethod
    def verify_device_token(token: str, expected_hash: str) -> bool:
        return TokenService._verify_secret(token, expected_hash)

    @staticmethod
    def generate_pairing_code() -> str:
        """Return exactly six decimal digits, retaining leading zeroes."""
        value = secrets.randbelow(10**PAIRING_CODE_DIGITS)
        return f"{value:0{PAIRING_CODE_DIGITS}d}"

    @staticmethod
    def hash_pairing_code(code: str) -> str:
        return TokenService._hash_secret(code)

    @staticmethod
    def verify_pairing_code(code: str, expected_hash: str) -> bool:
        return TokenService._verify_secret(code, expected_hash)

    @staticmethod
    def _hash_secret(secret: str) -> str:
        if not isinstance(secret, str):
            raise TypeError("secret must be a string")
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _verify_secret(secret: str, expected_hash: str) -> bool:
        if not isinstance(secret, str) or not isinstance(expected_hash, str):
            return False
        actual_hash = TokenService._hash_secret(secret)
        return hmac.compare_digest(actual_hash, expected_hash)
