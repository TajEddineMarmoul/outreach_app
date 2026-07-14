from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet_key_from_env() -> bytes:
    raw = os.getenv("APP_ENCRYPTION_KEY", "").strip()
    if not raw:
        env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").lower()
        if env in {"production", "prod"}:
            raise RuntimeError("APP_ENCRYPTION_KEY is required to encrypt OAuth credentials.")
        raw = "local-development-only-change-me"

    encoded = raw.encode("utf-8")
    try:
        Fernet(encoded)
        return encoded
    except Exception:
        digest = hashlib.sha256(encoded).digest()
        return base64.urlsafe_b64encode(digest)


def encrypt_text(value: str) -> str:
    return Fernet(_fernet_key_from_env()).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    try:
        return Fernet(_fernet_key_from_env()).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Encrypted credentials cannot be decrypted because APP_ENCRYPTION_KEY does not match."
        ) from exc
