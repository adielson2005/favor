"""Gateway abstraction. Nothing above this layer (routes, WalletService) should ever
import a gateway SDK directly — they call PaymentProvider methods, and only the
concrete provider below knows about ASAAS/whoever. Swapping providers later means
writing one new class here, not touching the frontend or the routes.

AsaasProvider.create_pix_charge and get_payment_status are real HTTP calls against
ASAAS's documented API (confirmed directly against docs.asaas.com before writing
this, not guessed) — everything else (create_payout, cancel_payment, refund_payment)
stays honestly unimplemented: no route in this app calls them yet (withdrawals are
still manual), and writing HTTP calls with no caller would just be dead code.
UnconfiguredProvider is what runs when PAYMENT_PROVIDER isn't "asaas" — every call
fails clearly instead of silently no-opping.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional

import requests
from fastapi.concurrency import run_in_threadpool

from asaas_customers import get_or_create_asaas_customer
from database import now


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
    async def create_pix_charge(self, amount_cents: int, reference: str, user_id: str, name: str,
                                 document: Optional[str] = None, description: str = "") -> dict:
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

    async def create_pix_charge(self, amount_cents: int, reference: str, user_id: str, name: str,
                                 document: Optional[str] = None, description: str = "") -> dict:
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
    """Real HTTP calls against ASAAS's REST API. Reads credentials from the
    environment only — never accept them from a request.
    """
    name = "asaas"

    def __init__(self):
        self.api_key = os.environ.get("ASAAS_API_KEY", "")
        self.base_url = os.environ.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
        self.webhook_secret = os.environ.get("ASAAS_WEBHOOK_SECRET", "")
        if not self.api_key:
            raise PaymentProviderUnavailable("ASAAS_API_KEY não configurada.")

    def _headers(self) -> dict:
        return {"access_token": self.api_key, "Content-Type": "application/json"}

    def _create_payment_sync(self, asaas_customer_id: str, amount_cents: int, reference: str, description: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/payments", headers=self._headers(),
            json={
                "customer": asaas_customer_id, "billingType": "PIX", "value": round(amount_cents / 100, 2),
                "dueDate": now()[:10], "externalReference": reference, "description": description,
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            raise PaymentProviderError(f"ASAAS recusou a cobrança: {resp.text}")
        return resp.json()

    def _get_pix_qr_code_sync(self, payment_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/payments/{payment_id}/pixQrCode", headers=self._headers(), timeout=15)
        if resp.status_code >= 400:
            raise PaymentProviderError(f"ASAAS não devolveu o QR code: {resp.text}")
        return resp.json()

    def _get_status_sync(self, payment_id: str) -> str:
        resp = requests.get(f"{self.base_url}/payments/{payment_id}/status", headers=self._headers(), timeout=15)
        if resp.status_code >= 400:
            raise PaymentProviderError(f"ASAAS não devolveu o status: {resp.text}")
        return resp.json()["status"]

    async def create_pix_charge(self, amount_cents: int, reference: str, user_id: str, name: str,
                                 document: Optional[str] = None, description: str = "") -> dict:
        # CpfRequiredError propagates as-is — routes/wallet.py's create_deposit
        # translates it into a 400 asking for CPF/CNPJ, distinct from the generic
        # "provider unavailable" case this method never raises once it gets here.
        asaas_customer_id = await get_or_create_asaas_customer(user_id, name, document)
        payment = await run_in_threadpool(self._create_payment_sync, asaas_customer_id, amount_cents, reference, description)
        qr = await run_in_threadpool(self._get_pix_qr_code_sync, payment["id"])
        return {
            "id": payment["id"], "status": payment.get("status"),
            "qr_code_image": qr.get("encodedImage"), "qr_code_payload": qr.get("payload"),
            "expires_at": qr.get("expirationDate"),
        }

    async def create_payout(self, amount_cents: int, bank_account: dict, reference: str) -> dict:
        raise NotImplementedError("Saques continuam manuais — nenhuma rota chama create_payout ainda.")

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        return await run_in_threadpool(self._get_status_sync, provider_transaction_id)

    async def cancel_payment(self, provider_transaction_id: str) -> dict:
        raise NotImplementedError("Sem call site hoje — implementar quando alguma rota precisar cancelar uma cobrança.")

    async def refund_payment(self, provider_transaction_id: str, amount_cents: int) -> dict:
        raise NotImplementedError("Sem call site hoje — implementar quando alguma rota precisar estornar.")


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
