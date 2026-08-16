"""Gateway abstraction. Nothing above this layer (routes, WalletService) should ever
import a gateway SDK directly — they call PaymentProvider methods, and only the
concrete provider below knows about ASAAS/whoever. Swapping providers later means
writing one new class here, not touching the frontend or the routes.

No real gateway is wired in yet. AsaasProvider exists as the target shape for when
real credentials show up (ASAAS_API_KEY etc., backend-only, see .env) — its methods
are honest about not being implemented rather than faking success. UnconfiguredProvider
is what actually runs today: every call fails clearly instead of silently no-opping.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional


class PaymentProviderError(Exception):
    def __init__(self, message: str, code: str = "provider_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class PaymentProviderUnavailable(PaymentProviderError):
    def __init__(self, message: str = "Nenhum provedor de pagamento está configurado neste servidor."):
        super().__init__(message, code="provider_unavailable")


class PaymentProvider(ABC):
    name: str = "unconfigured"

    @abstractmethod
    async def create_pix_charge(self, amount_cents: int, reference: str, description: str = "") -> dict:
        ...

    @abstractmethod
    async def create_payout(self, amount_cents: int, bank_account: dict, reference: str) -> dict:
        ...

    @abstractmethod
    async def get_payment_status(self, provider_transaction_id: str) -> str:
        ...

    @abstractmethod
    async def cancel_payment(self, provider_transaction_id: str) -> dict:
        ...

    @abstractmethod
    async def refund_payment(self, provider_transaction_id: str, amount_cents: int) -> dict:
        ...


class UnconfiguredProvider(PaymentProvider):
    name = "unconfigured"

    async def create_pix_charge(self, amount_cents: int, reference: str, description: str = "") -> dict:
        raise PaymentProviderUnavailable()

    async def create_payout(self, amount_cents: int, bank_account: dict, reference: str) -> dict:
        raise PaymentProviderUnavailable()

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        raise PaymentProviderUnavailable()

    async def cancel_payment(self, provider_transaction_id: str) -> dict:
        raise PaymentProviderUnavailable()

    async def refund_payment(self, provider_transaction_id: str, amount_cents: int) -> dict:
        raise PaymentProviderUnavailable()


class AsaasProvider(PaymentProvider):
    """Target shape for the real integration. Reads credentials from the environment
    only — never accept them from a request. Methods raise until the HTTP calls to
    ASAAS_BASE_URL are actually written and tested against real sandbox credentials;
    that's deliberate, per the "don't fake the integration" requirement.
    """
    name = "asaas"

    def __init__(self):
        self.api_key = os.environ.get("ASAAS_API_KEY", "")
        self.base_url = os.environ.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
        self.webhook_secret = os.environ.get("ASAAS_WEBHOOK_SECRET", "")
        if not self.api_key:
            raise PaymentProviderUnavailable("ASAAS_API_KEY não configurada.")

    async def create_pix_charge(self, amount_cents: int, reference: str, description: str = "") -> dict:
        raise NotImplementedError("Integração ASAAS ainda não implementada — configure credenciais reais e implemente a chamada HTTP.")

    async def create_payout(self, amount_cents: int, bank_account: dict, reference: str) -> dict:
        raise NotImplementedError("Integração ASAAS ainda não implementada.")

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        raise NotImplementedError("Integração ASAAS ainda não implementada.")

    async def cancel_payment(self, provider_transaction_id: str) -> dict:
        raise NotImplementedError("Integração ASAAS ainda não implementada.")

    async def refund_payment(self, provider_transaction_id: str, amount_cents: int) -> dict:
        raise NotImplementedError("Integração ASAAS ainda não implementada.")


_provider: Optional[PaymentProvider] = None


def get_payment_provider() -> PaymentProvider:
    global _provider
    if _provider is not None:
        return _provider
    name = os.environ.get("PAYMENT_PROVIDER", "none").lower()
    if name == "asaas":
        _provider = AsaasProvider()
    else:
        _provider = UnconfiguredProvider()
    return _provider
