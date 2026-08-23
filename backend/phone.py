"""Brazilian phone number normalization to E.164, shared by registration and phone-change."""
import re

from fastapi import HTTPException

_DIGITS_RE = re.compile(r"\D+")


def normalize_phone_br(raw: str) -> str:
    if not raw:
        raise HTTPException(400, "Telefone é obrigatório.")
    digits = _DIGITS_RE.sub("", raw)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) not in (10, 11):
        raise HTTPException(400, "Telefone inválido. Use o formato (DDD) 9XXXX-XXXX.")
    ddd = int(digits[:2])
    if not (11 <= ddd <= 99):
        raise HTTPException(400, "DDD inválido.")
    subscriber = digits[2:]
    if len(subscriber) == 9 and subscriber[0] != "9":
        raise HTTPException(400, "Número de celular deve começar com 9 após o DDD.")
    return f"+55{digits}"
