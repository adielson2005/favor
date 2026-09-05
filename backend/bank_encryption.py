"""Field-level encryption for bank-account PII (CPF/CNPJ + account number) at rest.

Fernet gives authenticated encryption (AES-128-CBC + HMAC), not just obfuscation —
a tampered ciphertext fails to decrypt rather than silently returning garbage.

Ciphertext is prefixed so decrypt_field() can tell it apart from the plaintext
values written before this module existed: those pass through unchanged instead
of erroring, so the migration script (scripts/encrypt_bank_data.py) can convert
them at its own pace without a hard cutover.
"""
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"


@lru_cache
def _fernet() -> Fernet:
    key = os.environ.get("BANK_DATA_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("BANK_DATA_ENCRYPTION_KEY não está configurada neste ambiente.")
    return Fernet(key.encode())


def encrypt_field(value: str) -> str:
    if not value:
        return value
    return _PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value  # legacy plaintext (pre-migration) or empty — pass through as-is
    token = value[len(_PREFIX):]
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return value
