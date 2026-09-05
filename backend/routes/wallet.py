import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from asaas_customers import AsaasCustomerRejectedError, CpfRequiredError
from auth import get_current_user, rate_limit, verify_password
from bank_encryption import decrypt_field, encrypt_field
from database import db, new_id, now
from fraud import check_withdrawal_risk, create_risk_flag
from models import (
    BankAccountIn, BankAccountRemoveIn, DepositIn, DisputeIn, WithdrawalIn,
)
from payments import PaymentProviderError, PaymentProviderUnavailable, get_payment_provider
from security_events import log_security_event
from verification import require_active_account
from wallet import (
    InsufficientFundsError, credit_wallet, debit_wallet, get_commission_config,
    get_or_create_wallet, move_bucket, to_cents, to_reais, transaction_public, wallet_public,
)

router = APIRouter()

MAX_IMAGE_B64_CHARS = 2_000_000
ALLOWED_IMAGE_PREFIXES = ("data:image/jpeg", "data:image/jpg", "data:image/png", "data:image/webp")


def mask_account(account: dict) -> dict:
    number = decrypt_field(account.get("account_number", ""))
    masked = f"****{number[-4:]}" if len(number) >= 4 else "****"
    doc = decrypt_field(account.get("document", ""))
    masked_doc = f"***.***.***-{doc[-2:]}" if len(doc) >= 2 else "***"
    return {k: account.get(k) for k in ("id", "holder_name", "bank_code", "agency", "account_type", "is_primary", "created_at")} | {
        "account_number_masked": masked, "document_masked": masked_doc,
    }


# ---------- wallet ----------

@router.get("/wallet")
async def get_wallet(current=Depends(get_current_user)):
    wallet = await get_or_create_wallet(current["id"])
    return wallet_public(wallet)


@router.get("/wallet/transactions")
async def wallet_transactions(
    type: Optional[str] = None, status: Optional[str] = None, direction: Optional[str] = None,
    limit: int = 30, offset: int = 0, current=Depends(get_current_user),
):
    query: dict = {"user_id": current["id"]}
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    if direction:
        query["direction"] = direction
    items = await db.wallet_transactions.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 100))
    return [transaction_public(t) for t in items]


# ---------- deposits ----------

@router.post("/wallet/deposits")
async def create_deposit(body: DepositIn, current=Depends(get_current_user), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    rate_limit(f"deposit:{current['id']}", max_attempts=10, window_seconds=600)
    config = await get_commission_config()
    if body.amount > config["max_deposit_per_transaction"]:
        raise HTTPException(400, f"O valor máximo por depósito é R$ {config['max_deposit_per_transaction']:.2f}.")
    if idempotency_key:
        existing = await db.deposits.find_one({"idempotency_key": idempotency_key}, {"_id": 0})
        if existing:
            return existing
    deposit = {
        "id": new_id(), "user_id": current["id"], "amount": body.amount, "method": body.method,
        "status": "PENDING", "provider": None, "provider_transaction_id": None,
        "created_at": now(), "updated_at": now(),
    }
    if idempotency_key:
        deposit["idempotency_key"] = idempotency_key
    provider = get_payment_provider()
    try:
        result = await provider.create_pix_charge(
            to_cents(body.amount), reference=deposit["id"], user_id=current["id"], name=current["name"],
            document=body.document, description="Depósito fazum",
        )
        deposit["status"] = "PROCESSING"
        deposit["provider"] = provider.name
        deposit["provider_transaction_id"] = result.get("id")
        deposit["qr_code_image"] = result.get("qr_code_image")
        deposit["qr_code_payload"] = result.get("qr_code_payload")
        deposit["expires_at"] = result.get("expires_at")
    except CpfRequiredError:
        # Not a provider failure — the gateway is configured and working, this
        # specific user just doesn't have a CPF/CNPJ on file yet. No deposit row
        # is created; the client resubmits the same request with `document` set.
        raise HTTPException(400, "Precisamos do seu CPF ou CNPJ para gerar o Pix.")
    except AsaasCustomerRejectedError as e:
        deposit["status"] = "FAILED"
        await db.deposits.insert_one(dict(deposit))
        raise HTTPException(400, e.message)
    except PaymentProviderUnavailable:
        deposit["status"] = "FAILED"
        await db.deposits.insert_one(dict(deposit))
        raise HTTPException(501, "Depósito ainda não está disponível — nenhum provedor de pagamento foi configurado neste servidor.")
    except PaymentProviderError as e:
        deposit["status"] = "FAILED"
        await db.deposits.insert_one(dict(deposit))
        raise HTTPException(400, e.message)
    await db.deposits.insert_one(dict(deposit))
    return {k: v for k, v in deposit.items() if k != "_id"}


@router.get("/wallet/deposits/{deposit_id}")
async def get_deposit(deposit_id: str, current=Depends(get_current_user)):
    deposit = await db.deposits.find_one({"id": deposit_id}, {"_id": 0})
    if not deposit or deposit["user_id"] != current["id"]:
        raise HTTPException(404, "Depósito não encontrado.")
    return deposit


# ---------- bank accounts ----------

@router.get("/bank-accounts")
async def list_bank_accounts(current=Depends(get_current_user)):
    accounts = await db.bank_accounts.find({"user_id": current["id"], "active": True}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return [mask_account(a) for a in accounts]


@router.post("/bank-accounts")
async def add_bank_account(body: BankAccountIn, request: Request, current=Depends(get_current_user)):
    rate_limit(f"add-bank-account:{current['id']}", max_attempts=10, window_seconds=3600)
    require_active_account(current)
    if not verify_password(body.password, current.get("password_hash") or ""):
        raise HTTPException(401, "Senha incorreta.")
    if not body.document.isdigit():
        raise HTTPException(400, "CPF/CNPJ deve conter apenas números.")
    existing_count = await db.bank_accounts.count_documents({"user_id": current["id"], "active": True})
    account = {
        "id": new_id(), "user_id": current["id"], "holder_name": body.holder_name.strip(),
        "document": body.document, "bank_code": body.bank_code, "agency": body.agency,
        "account_number": body.account_number, "account_type": body.account_type,
        "is_primary": existing_count == 0, "active": True, "created_at": now(),
    }
    # CPF/CNPJ and account number are the only fields worth encrypting at rest here —
    # everything else (bank code, agency, holder name) is already low-sensitivity or
    # shown in full elsewhere. `account` (plaintext) is kept for the notification text
    # and the mask_account() call below; only the stored copy is encrypted.
    stored = {**account, "document": encrypt_field(account["document"]), "account_number": encrypt_field(account["account_number"])}
    await db.bank_accounts.insert_one(stored)
    await log_security_event(current["id"], "bank_account_added", detail=account["id"], ip=request.client.host if request.client else None)
    await db.notifications.insert_one({
        "id": new_id(), "user_id": current["id"], "title": "Conta bancária adicionada",
        "body": f"Uma conta terminada em {account['account_number'][-4:]} foi adicionada para saques.",
        "type": "bank_account", "order_id": None, "read": False, "created_at": now(),
    })
    return mask_account(account)


@router.patch("/bank-accounts/{account_id}/primary")
async def set_primary_bank_account(account_id: str, current=Depends(get_current_user)):
    rate_limit(f"set-primary-bank-account:{current['id']}", max_attempts=20, window_seconds=3600)
    account = await db.bank_accounts.find_one({"id": account_id, "user_id": current["id"], "active": True})
    if not account:
        raise HTTPException(404, "Conta não encontrada.")
    await db.bank_accounts.update_many({"user_id": current["id"]}, {"$set": {"is_primary": False}})
    await db.bank_accounts.update_one({"id": account_id}, {"$set": {"is_primary": True}})
    return {"ok": True}


@router.delete("/bank-accounts/{account_id}")
async def remove_bank_account(account_id: str, body: BankAccountRemoveIn, request: Request, current=Depends(get_current_user)):
    rate_limit(f"remove-bank-account:{current['id']}", max_attempts=10, window_seconds=3600)
    if not verify_password(body.password, current.get("password_hash") or ""):
        raise HTTPException(401, "Senha incorreta.")
    account = await db.bank_accounts.find_one({"id": account_id, "user_id": current["id"]})
    if not account:
        raise HTTPException(404, "Conta não encontrada.")
    await db.bank_accounts.update_one({"id": account_id}, {"$set": {"active": False}})
    await log_security_event(current["id"], "bank_account_removed", detail=account_id, ip=request.client.host if request.client else None)
    return {"ok": True}


# ---------- withdrawals ----------

@router.post("/wallet/withdrawals")
async def create_withdrawal(body: WithdrawalIn, request: Request, current=Depends(get_current_user), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    rate_limit(f"withdrawal:{current['id']}", max_attempts=10, window_seconds=600)
    require_active_account(current)
    if not verify_password(body.password, current.get("password_hash") or ""):
        raise HTTPException(401, "Senha incorreta.")
    config = await get_commission_config()
    if body.amount < config["min_withdrawal"]:
        raise HTTPException(400, f"O valor mínimo de saque é R$ {config['min_withdrawal']:.2f}.")
    max_per_day = config.get("max_withdrawal_per_day")
    if max_per_day:
        # Admin-configured daily cash cap — previously accepted via PATCH /admin/config
        # but never actually enforced anywhere. Same "today" convention as fraud.py's
        # own daily withdrawal count (ISO date prefix on created_at).
        since = now()[:10]
        today_total = 0.0
        async for w in db.withdrawals.find(
            {"user_id": current["id"], "created_at": {"$gte": since}, "status": {"$in": ["PENDING", "REVIEW_REQUIRED", "COMPLETED"]}},
            {"amount": 1},
        ):
            today_total += w["amount"]
        if today_total + body.amount > max_per_day:
            raise HTTPException(400, f"Esse saque ultrapassa o limite diário de R$ {max_per_day:.2f}. Você já solicitou R$ {today_total:.2f} hoje.")
    account = await db.bank_accounts.find_one({"id": body.bank_account_id, "user_id": current["id"], "active": True}, {"_id": 0})
    if not account:
        raise HTTPException(404, "Conta bancária não encontrada.")
    if idempotency_key:
        existing = await db.withdrawals.find_one({"idempotency_key": idempotency_key}, {"_id": 0})
        if existing:
            return existing

    amount_cents = to_cents(body.amount)
    client_ip = request.client.host if request.client else None
    risk, risk_reasons = await check_withdrawal_risk(current, amount_cents, account, client_ip=client_ip)
    if risk == "CRITICAL":
        await create_risk_flag(current["id"], "withdrawal_attempt", body.bank_account_id, risk, risk_reasons)
        raise HTTPException(403, "Não foi possível processar este saque agora. Nossa equipe entrará em contato.")
    # HIGH keeps the same persisted withdrawal status ("REVIEW_REQUIRED") the frontend
    # already knows how to render — only the risk scale underneath got richer.
    status = "REVIEW_REQUIRED" if risk == "HIGH" else "PENDING"
    withdrawal_id = new_id()
    if risk == "HIGH":
        await create_risk_flag(current["id"], "withdrawal", withdrawal_id, risk, risk_reasons)

    try:
        # Atomically hold the funds — available -> processing. This is the operation
        # that actually prevents withdrawing more than the balance, including under
        # concurrent requests; everything after this point is just bookkeeping.
        await move_bucket(current["id"], amount_cents, "available", "processing", "WITHDRAWAL",
                           reference_type="withdrawal", reference_id=withdrawal_id, description="Saque solicitado")
    except InsufficientFundsError:
        raise HTTPException(400, "Saldo disponível insuficiente para esse saque.")

    withdrawal = {
        "id": withdrawal_id, "user_id": current["id"], "amount": body.amount, "bank_account_id": account["id"],
        "bank_account_snapshot": mask_account(account), "status": status, "risk_level": risk, "risk_reasons": risk_reasons,
        "created_at": now(), "updated_at": now(),
    }
    if idempotency_key:
        withdrawal["idempotency_key"] = idempotency_key
    await db.withdrawals.insert_one(dict(withdrawal))
    await db.notifications.insert_one({
        "id": new_id(), "user_id": current["id"], "title": "Saque solicitado",
        "body": f"Seu saque de R$ {body.amount:.2f} está {('em análise' if status == 'REVIEW_REQUIRED' else 'sendo processado')}.",
        "type": "withdrawal", "order_id": None, "read": False, "created_at": now(),
    })
    withdrawal.pop("_id", None)
    return withdrawal


@router.get("/wallet/withdrawals")
async def list_withdrawals(current=Depends(get_current_user)):
    return await db.withdrawals.find({"user_id": current["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.post("/wallet/withdrawals/{withdrawal_id}/cancel")
async def cancel_withdrawal(withdrawal_id: str, current=Depends(get_current_user)):
    rate_limit(f"cancel-withdrawal:{current['id']}", max_attempts=10, window_seconds=600)
    withdrawal = await db.withdrawals.find_one({"id": withdrawal_id, "user_id": current["id"]})
    if not withdrawal:
        raise HTTPException(404, "Saque não encontrado.")
    if withdrawal["status"] not in ("PENDING", "REVIEW_REQUIRED"):
        raise HTTPException(400, "Esse saque não pode mais ser cancelado.")
    await move_bucket(current["id"], to_cents(withdrawal["amount"]), "processing", "available", "WITHDRAWAL",
                       reference_type="withdrawal", reference_id=withdrawal_id, description="Saque cancelado pelo usuário")
    await db.withdrawals.update_one({"id": withdrawal_id}, {"$set": {"status": "CANCELLED", "updated_at": now()}})
    return {"ok": True, "status": "CANCELLED"}


# ---------- disputes ----------

@router.post("/disputes")
async def create_dispute(body: DisputeIn, current=Depends(get_current_user)):
    rate_limit(f"dispute:{current['id']}", max_attempts=10, window_seconds=3600)
    order = await db.orders.find_one({"id": body.order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado.")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa deste pedido.")
    for img in body.evidence:
        if not img.startswith(ALLOWED_IMAGE_PREFIXES) or len(img) > MAX_IMAGE_B64_CHARS:
            raise HTTPException(400, "Uma das evidências enviadas é inválida.")
    dispute = {
        "id": new_id(), "order_id": body.order_id, "reporter_id": current["id"],
        "target_type": body.target_type, "reason": body.reason, "description": body.description,
        "evidence": body.evidence, "status": "OPEN", "resolution": "", "created_at": now(), "updated_at": now(),
    }
    await db.disputes.insert_one(dict(dispute))
    # Best-effort lock: while the order is still "live" (accepted/in_progress/
    # completion_requested), a dispute freezes it in `disputed` so start/complete/cancel
    # can't run concurrently — their atomic guards simply stop matching once the status
    # isn't one of theirs anymore, no changes needed on those endpoints. A dispute about
    # an already-completed/cancelled order is still valid to open — there's just nothing
    # left in the lifecycle to freeze.
    locked = await db.orders.find_one_and_update(
        {"id": body.order_id, "status": {"$in": ["accepted", "in_progress", "completion_requested"]}},
        {"$set": {"status": "disputed", "pre_dispute_status": order["status"]}},
    )
    if locked:
        counterpart = order["worker_id"] if current["id"] == order["client_id"] else order["client_id"]
        if counterpart:
            await db.notifications.insert_one({
                "id": new_id(), "user_id": counterpart, "title": "Disputa aberta",
                "body": f"Uma disputa foi aberta em “{order['title']}”. O pedido ficou em análise.",
                "type": "dispute", "order_id": body.order_id, "read": False, "created_at": now(),
            })
    dispute.pop("_id", None)
    return dispute


@router.get("/disputes")
async def list_my_disputes(current=Depends(get_current_user)):
    return await db.disputes.find({"reporter_id": current["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


# ---------- webhook ----------

DEPOSIT_RECEIVED_EVENTS = ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED")
DEPOSIT_FAILED_EVENTS = ("PAYMENT_OVERDUE", "PAYMENT_DELETED")
DEPOSIT_REFUND_EVENTS = ("PAYMENT_REFUNDED", "PAYMENT_PARTIALLY_REFUNDED")


async def _find_deposit_for_payment(payment: dict) -> Optional[dict]:
    provider_txn_id = payment.get("id")
    if provider_txn_id:
        deposit = await db.deposits.find_one({"provider_transaction_id": provider_txn_id})
        if deposit:
            return deposit
    external_ref = payment.get("externalReference")
    if external_ref:
        return await db.deposits.find_one({"id": external_ref})
    return None


async def _reconcile_deposit_event(event: str, payload: dict) -> None:
    payment = payload.get("payment") or {}
    deposit = await _find_deposit_for_payment(payment)
    if not deposit:
        return

    if event in DEPOSIT_RECEIVED_EVENTS and deposit["status"] == "PROCESSING":
        await credit_wallet(
            user_id=deposit["user_id"], amount_cents=to_cents(deposit["amount"]), type_="DEPOSIT",
            reference_type="deposit", reference_id=deposit["id"], provider="asaas",
            provider_transaction_id=payment.get("id"), description="Depósito via PIX confirmado",
            idempotency_key=f"deposit-credit:{deposit['id']}",
        )
        await db.deposits.update_one({"id": deposit["id"]}, {"$set": {
            "status": "COMPLETED", "provider_transaction_id": payment.get("id"), "updated_at": now(),
        }})
    elif event in DEPOSIT_FAILED_EVENTS and deposit["status"] in ("PENDING", "PROCESSING"):
        await db.deposits.update_one({"id": deposit["id"]}, {"$set": {"status": "FAILED", "updated_at": now()}})
    elif event in DEPOSIT_REFUND_EVENTS and deposit["status"] == "COMPLETED":
        try:
            await debit_wallet(
                user_id=deposit["user_id"], amount_cents=to_cents(deposit["amount"]), type_="DEPOSIT_REFUND",
                reference_type="deposit", reference_id=deposit["id"], description="Estorno de depósito via PIX",
                idempotency_key=f"deposit-refund:{deposit['id']}", count_as_spent=False,
            )
            await db.deposits.update_one({"id": deposit["id"]}, {"$set": {"status": "REFUNDED", "updated_at": now()}})
        except InsufficientFundsError:
            # Saldo já foi gasto pelo usuário — não dá pra estornar automaticamente sem
            # deixar a carteira negativa. Registrado para revisão manual de um admin em
            # vez de fingir sucesso ou derrubar o webhook (que precisa sempre voltar 200
            # para a ASAAS não entrar em loop de retentativa).
            await db.deposits.update_one({"id": deposit["id"]}, {"$set": {"status": "REFUND_NEEDS_REVIEW", "updated_at": now()}})
            await log_security_event(deposit["user_id"], "deposit_refund_needs_manual_review", detail=deposit["id"])


@router.post("/webhooks/payment-provider")
async def payment_webhook(request: Request):
    secret = os.environ.get("ASAAS_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(501, "Webhook não configurado neste servidor.")
    # A ASAAS não assina o corpo — ela ecoa de volta um token estático (configurado no
    # painel ASAAS) neste header, a cada chamada. Comparação direta, não HMAC do payload.
    token = request.headers.get("asaas-access-token", "")
    if not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Token de acesso inválido.")
    payload = await request.json()
    event_id = payload.get("id") or payload.get("event")
    if not event_id:
        raise HTTPException(400, "Evento inválido.")
    if await db.payment_events.find_one({"event_id": event_id}):
        return {"ok": True, "duplicate": True}
    await db.payment_events.insert_one({"id": new_id(), "event_id": event_id, "payload": payload, "processed_at": now()})
    await _reconcile_deposit_event(payload.get("event", ""), payload)
    return {"ok": True}
