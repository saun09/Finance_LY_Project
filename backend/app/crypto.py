"""Application-level encryption at rest for sensitive columns.

Values are encrypted with AES-256-GCM (authenticated: a tampered or
wrong-key ciphertext fails to decrypt rather than returning garbage) before
they reach the database, and decrypted transparently when loaded. Models opt
in per column with the `Encrypted*` types below; the Python attribute keeps
its plain type (int, str, Decimal, dict) so services don't change.

Stored format: ``enc:v1:<urlsafe-base64(12-byte nonce || ciphertext+tag)>``.
A fresh random nonce per value means equal plaintexts produce different
ciphertexts, so encrypted columns can't be filtered, sorted, summed or
uniquely-indexed in SQL -- only encrypt columns that are only ever read back
into Python. Lookup keys (`user_id`, `username`, enums used in WHERE
clauses, timestamps) stay plaintext for that reason.

The key comes from the DATA_ENCRYPTION_KEY env var (urlsafe-base64 of 32
random bytes; generate with `python -m app.crypto`). Losing it makes every
encrypted value unrecoverable, so keep it in a secret manager / Render env
vars, never in git.
"""

import base64
import json
import os
import secrets
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

PREFIX = "enc:v1:"
_NONCE_BYTES = 12


class EncryptionKeyError(RuntimeError):
    pass


def generate_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


@lru_cache(maxsize=1)
def _aesgcm() -> AESGCM:
    # Read lazily (not at import) so tests and Alembic can set the env var
    # before first use, and so a missing key fails on the first DB write/read
    # with a clear message instead of an import-time crash elsewhere.
    raw = os.environ.get("DATA_ENCRYPTION_KEY")
    if not raw:
        raise EncryptionKeyError(
            "DATA_ENCRYPTION_KEY is not set; generate one with `python -m app.crypto` "
            "and put it in backend/.env (or the host's env vars)"
        )
    try:
        key = base64.urlsafe_b64decode(raw)
    except ValueError as exc:
        raise EncryptionKeyError("DATA_ENCRYPTION_KEY is not valid urlsafe base64") from exc
    if len(key) != 32:
        raise EncryptionKeyError("DATA_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
    return AESGCM(key)


def encrypt(plaintext: str) -> str:
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = _aesgcm().encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt(token: str) -> str:
    if not token.startswith(PREFIX):
        # Never fall back to treating it as plaintext: an unencrypted value
        # here means a row skipped the 0008 migration, which should be loud.
        raise ValueError("value is not encrypted (missing enc:v1: prefix)")
    blob = base64.urlsafe_b64decode(token[len(PREFIX):])
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return _aesgcm().decrypt(nonce, ciphertext, None).decode("utf-8")


class _EncryptedType(TypeDecorator):
    # SQLAlchemy reads cache_ok from each subclass's own __dict__, so every
    # concrete type below re-declares it.
    impl = Text
    cache_ok = True

    def _serialize(self, value: Any) -> str:
        raise NotImplementedError

    def _deserialize(self, text: str) -> Any:
        raise NotImplementedError

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(self._serialize(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._deserialize(decrypt(value))


class EncryptedInteger(_EncryptedType):
    cache_ok = True

    def _serialize(self, value: Any) -> str:
        return str(int(value))

    def _deserialize(self, text: str) -> int:
        return int(text)


class EncryptedString(_EncryptedType):
    cache_ok = True

    def _serialize(self, value: Any) -> str:
        return str(value)

    def _deserialize(self, text: str) -> str:
        return text


class EncryptedDecimal(_EncryptedType):
    """Quantizes to `scale` on write, matching the NUMERIC(p, scale) column
    this replaced, so stored ratios round exactly as they did before."""

    cache_ok = True

    def __init__(self, scale: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scale = scale

    def _serialize(self, value: Any) -> str:
        quantum = Decimal(1).scaleb(-self.scale)
        return str(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))

    def _deserialize(self, text: str) -> Decimal:
        return Decimal(text)


class EncryptedJSON(_EncryptedType):
    cache_ok = True

    def _serialize(self, value: Any) -> str:
        return json.dumps(value)

    def _deserialize(self, text: str) -> Any:
        return json.loads(text)


if __name__ == "__main__":
    print(generate_key())
