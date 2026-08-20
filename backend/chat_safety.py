"""Detects likely attempts to move a deal's payment/negotiation outside fazum —
Pix-key-shaped strings, phone numbers, and common Portuguese "pay me directly"
phrases. Deliberately non-blocking on text: we can't reliably censor a Pix key
out of a chat message, so this only ever *scores* the message; `routes/public.py`
decides what happens with the score (warn -> repeat -> analyze -> restrict).
"""
import re
import unicodedata

_PHRASES = [
    "pague por fora", "paga por fora", "pagar por fora", "fora do app", "fora da plataforma",
    "fora do fazum", "manda direto", "manda por fora", "sem taxa", "sem comissao",
    "combinamos por fora", "combina por fora", "te passo o pix", "passo o pix",
    "chama no whatsapp", "chama no zap", "meu whatsapp", "meu numero e", "meu zap",
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CPF_RE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_PHONE_SHAPE_RE = re.compile(r"\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}")


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def scan_message_for_external_payment(text: str) -> list[str]:
    """Returns the sorted list of matched signal categories — empty if the message
    looks clean. Categories: 'pix_key' (email/CPF/UUID-shaped Pix key), 'phone'
    (a phone-number-shaped digit run), 'phrase' (a known external-payment phrase)."""
    if not text:
        return []
    categories: set[str] = set()

    if _EMAIL_RE.search(text) or _CPF_RE.search(text) or _UUID_RE.search(text):
        categories.add("pix_key")

    digits_only = re.sub(r"\D", "", text)
    if len(digits_only) >= 10 and _PHONE_SHAPE_RE.search(text):
        categories.add("phone")

    normalized = _normalize(text)
    if any(phrase in normalized for phrase in _PHRASES):
        categories.add("phrase")

    return sorted(categories)
