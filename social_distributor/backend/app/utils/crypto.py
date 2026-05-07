"""Symmetric encryption for OAuth tokens at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256). Key must be a 32-byte url-safe base64
value provided via TOKEN_ENCRYPTION_KEY. We never log decrypted token material.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from ..config import config


class TokenCipher:
    def __init__(self, key: str | None = None):
        key = key or config.token_encryption_key
        if not key:
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY is not set; refusing to handle tokens"
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Token decryption failed") from exc


_cipher: TokenCipher | None = None


def cipher() -> TokenCipher:
    global _cipher
    if _cipher is None:
        _cipher = TokenCipher()
    return _cipher
