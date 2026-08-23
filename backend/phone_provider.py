"""SMS/WhatsApp OTP delivery abstraction — same shape as payments.py's PaymentProvider,
so a real provider (Twilio, Zenvia, WhatsApp Business Cloud API...) can be dropped in
later by writing one new class here, without touching routes or the frontend.

No real provider is wired in yet (no SMS credentials exist). UnconfiguredPhoneProvider
is what runs today: send_otp is honest about not delivering anything rather than
pretending to — callers fall back to the same dev-mode "code in the API response"
pattern already used for email.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional


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
    """Target shape for a real integration. Reads credentials from the environment
    only — never accept them from a request. Not implemented; deliberately raises
    rather than faking delivery, matching payments.py's AsaasProvider."""
    name = "twilio"

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
        if not (self.account_sid and self.auth_token and self.from_number):
            raise RuntimeError("Credenciais Twilio incompletas.")

    async def send_otp(self, phone: str, code: str) -> bool:
        raise NotImplementedError("Integração Twilio ainda não implementada — configure credenciais reais e implemente a chamada HTTP.")


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
