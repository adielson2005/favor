"""SMS/WhatsApp OTP delivery abstraction — same shape as payments.py's PaymentProvider,
so a real provider (Twilio, Zenvia, WhatsApp Business Cloud API...) can be dropped in
later by writing one new class here, without touching routes or the frontend.

UnconfiguredPhoneProvider is what runs when SMS_PROVIDER isn't "twilio": send_otp is
honest about not delivering anything rather than pretending to — callers fall back to
the same dev-mode "code in the API response" pattern already used for email. That
fallback is fine for local testing but means phone verification is not a real check
once deployed with no provider configured, so TwilioPhoneProvider's real HTTP call
(below) matters for production the same way AsaasProvider's real PIX call does.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional

import requests
from fastapi.concurrency import run_in_threadpool


class PhoneProvider(ABC):
    name: str = "unconfigured"

    @abstractmethod
    async def send_otp(self, phone: str, code: str) -> bool:
        """Returns True only if the message was actually handed off to the carrier/API."""
        ...


class UnconfiguredPhoneProvider(PhoneProvider):
    name = "unconfigured"

    async def send_otp(self, phone: str, code: str) -> bool:
        return False


class TwilioPhoneProvider(PhoneProvider):
    """Real HTTP call against Twilio's documented Messages API (confirmed directly
    against twilio.com/docs before writing this, not guessed) — Basic Auth with the
    Account SID/Auth Token, same `requests` dependency payments.py already uses, no
    Twilio SDK needed. Reads credentials from the environment only — never accept
    them from a request."""
    name = "twilio"

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
        if not (self.account_sid and self.auth_token and self.from_number):
            raise RuntimeError("Credenciais Twilio incompletas.")

    def _send_sync(self, phone: str, code: str) -> bool:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            auth=(self.account_sid, self.auth_token),
            data={"To": phone, "From": self.from_number, "Body": f"Seu código fazum é {code}. Ele expira em 10 minutos."},
            timeout=10,
        )
        if resp.status_code >= 300:
            return False
        return True

    async def send_otp(self, phone: str, code: str) -> bool:
        return await run_in_threadpool(self._send_sync, phone, code)


_provider: Optional[PhoneProvider] = None


def get_phone_provider() -> PhoneProvider:
    global _provider
    if _provider is not None:
        return _provider
    name = os.environ.get("SMS_PROVIDER", "none").lower()
    if name == "twilio":
        _provider = TwilioPhoneProvider()
    else:
        _provider = UnconfiguredPhoneProvider()
    return _provider
