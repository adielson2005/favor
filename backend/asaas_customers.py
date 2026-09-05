"""Maps a FAZUM user_id to an ASAAS customer id. Creating a PIX charge on ASAAS
requires a `customer` — there's no "charge without a customer" call — and a
customer requires a CPF/CNPJ, which `users` doesn't store (only `bank_accounts`
does, and only for whoever has already added a payout account). This module is
the one place that CPF is collected for the deposit flow, mirroring exactly how
`bank_accounts` already collects+encrypts CPF for withdrawals.
"""
import os

import requests
from fastapi.concurrency import run_in_threadpool

from bank_encryption import encrypt_field
from database import db, new_id, now


class CpfRequiredError(Exception):
    """Raised when a user has no ASAAS customer on file and no document was
    provided to create one — the route turns this into a clear 400, never a
    generic 501 (that's reserved for "no provider configured at all")."""
    pass


class AsaasCustomerRejectedError(Exception):
    """Raised when ASAAS itself refuses to create the customer (e.g. an
    invalid CPF/CNPJ) — the route turns this into a 400 with ASAAS's own
    message instead of letting it fall through as an unhandled 500."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _asaas_headers() -> dict:
    return {"access_token": os.environ.get("ASAAS_API_KEY", ""), "Content-Type": "application/json"}


def _create_asaas_customer_sync(name: str, document: str, external_reference: str) -> str:
    base_url = os.environ.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
    resp = requests.post(
        f"{base_url}/customers",
        headers=_asaas_headers(),
        json={"name": name, "cpfCnpj": document, "externalReference": external_reference},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise AsaasCustomerRejectedError(f"ASAAS recusou o cadastro do cliente: {resp.text}")
    return resp.json()["id"]


async def get_or_create_asaas_customer(user_id: str, name: str, document: str | None) -> str:
    existing = await db.asaas_customers.find_one({"user_id": user_id})
    if existing:
        return existing["asaas_customer_id"]
    if not document:
        raise CpfRequiredError()
    asaas_customer_id = await run_in_threadpool(_create_asaas_customer_sync, name, document, user_id)
    await db.asaas_customers.insert_one({
        "id": new_id(), "user_id": user_id, "asaas_customer_id": asaas_customer_id,
        "document": encrypt_field(document), "created_at": now(),
    })
    return asaas_customer_id
