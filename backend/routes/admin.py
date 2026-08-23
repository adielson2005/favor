import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from admin_auth import require_permission
from auth import rate_limit
from database import db, new_id, now
from feature_flags import list_flags, set_flag
from models import (
    ActivePatch, AdminAccountStatusIn, AdminAdjustmentIn, AdminDisputeActionIn, AdminReportActionIn,
    AdminRiskFlagActionIn, AdminWithdrawalActionIn, CategoryIn, CommissionConfigIn, FeatureFlagPatchIn,
    GeoCityIn, GeoNeighborhoodIn, GeoStateIn, NotificationSendIn, SubcategoryIn,
)
from wallet import (
    PLATFORM_WALLET_USER_ID, InsufficientFundsError, credit_wallet, debit_wallet,
    get_commission_config, move_bucket, to_cents, wallet_public,
)

router = APIRouter(prefix="/admin")


async def log_action(admin_id: str, action: str, target: str, ip: Optional[str] = None,
                      result: str = "success", metadata: Optional[dict] = None):
    await db.admin_actions.insert_one({
        "id": new_id(), "admin_id": admin_id, "action": action, "target": target,
        "ip": ip, "result": result, "metadata": metadata or {}, "created_at": now(),
    })


async def notify(user_id: str, title: str, body: str, kind: str, order_id: Optional[str] = None):
    user = await db.users.find_one({"id": user_id}, {"notification_prefs": 1})
    if user and (user.get("notification_prefs") or {}).get(kind) is False:
        return
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "title": title, "body": body, "type": kind, "order_id": order_id, "read": False, "created_at": now()})


@router.get("/overview")
async def overview(admin=Depends(require_permission("dashboard.view"))):
    return {
        "users": await db.users.count_documents({}),
        "orders": await db.orders.count_documents({}),
        "orders_open": await db.orders.count_documents({"status": "published"}),
        "proposals": await db.proposals.count_documents({}),
        "reviews": await db.reviews.count_documents({}),
        "reports_open": await db.reports.count_documents({"status": "OPEN"}),
        "risk_flags_open": await db.risk_flags.count_documents({"status": "OPEN"}),
        "categories": await db.categories.count_documents({}),
        "neighborhoods": await db.neighborhoods.count_documents({}),
        "withdrawals_pending": await db.withdrawals.count_documents({"status": {"$in": ["PENDING", "REVIEW_REQUIRED"]}}),
        "disputes_open": await db.disputes.count_documents({"status": {"$nin": ["RESOLVED", "REJECTED", "CANCELLED"]}}),
    }


# ---------- users ----------

@router.get("/users")
async def users(search: Optional[str] = None, status: Optional[str] = None, city_id: Optional[str] = None,
                 limit: int = 200, offset: int = 0, admin=Depends(require_permission("users.view"))):
    query: dict = {}
    if search:
        pattern = re.escape(search.strip())
        query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
            {"phone": {"$regex": pattern, "$options": "i"}},
            {"id": search.strip()},
        ]
    if status:
        query["account_status"] = status
    if city_id:
        query["city_id"] = city_id
    total = await db.users.count_documents(query)
    items = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    return {"items": items, "total": total}


@router.get("/users/{user_id}")
async def user_detail(user_id: str, admin=Depends(require_permission("users.view"))):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    orders = await db.orders.find({"$or": [{"client_id": user_id}, {"worker_id": user_id}]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    payments = await db.payments.find({"$or": [{"client_id": user_id}, {"worker_id": user_id}]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    disputes = await db.disputes.find({"reporter_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    reports = await db.reports.find({"$or": [{"reporter_id": user_id}, {"target_type": "user", "target_id": user_id}]}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"user": user, "orders": orders, "payments": payments, "disputes": disputes, "reports": reports}


@router.post("/users/{user_id}/block")
async def toggle_block_user(user_id: str, admin=Depends(require_permission("users.block"))):
    rate_limit(f"admin-block-user:{admin['id']}", max_attempts=60, window_seconds=300)
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    blocked = not user.get("blocked", False)
    await db.users.update_one({"id": user_id}, {"$set": {"blocked": blocked}})
    await log_action(admin["id"], "block" if blocked else "unblock", f"user:{user_id}")
    return {"blocked": blocked}


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_user_sessions(user_id: str, admin=Depends(require_permission("users.sessions.revoke"))):
    rate_limit(f"admin-revoke-sessions:{admin['id']}", max_attempts=60, window_seconds=300)
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    await db.users.update_one({"id": user_id}, {"$inc": {"token_version": 1}})
    await log_action(admin["id"], "revoke_sessions", f"user:{user_id}")
    await notify(user_id, "Sessões encerradas", "Por segurança, encerramos seus acessos ativos. Entre novamente.", "security")
    return {"message": "Sessões encerradas."}


@router.patch("/users/{user_id}/status")
async def set_account_status(user_id: str, body: AdminAccountStatusIn, admin=Depends(require_permission("users.status.manage"))):
    rate_limit(f"admin-set-status:{admin['id']}", max_attempts=60, window_seconds=300)
    if body.status not in ("ACTIVE", "SUSPENDED", "BLOCKED", "PENDING_VERIFICATION"):
        raise HTTPException(400, "Status inválido.")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    # Keep the legacy `blocked` boolean (still what get_current_user checks on every
    # request) in lockstep with the new status, so this endpoint has real teeth and
    # the old block/unblock endpoint doesn't silently fight it.
    await db.users.update_one({"id": user_id}, {"$set": {
        "account_status": body.status, "blocked": body.status == "BLOCKED",
    }})
    await log_action(admin["id"], "set_account_status", f"user:{user_id}:{body.status}")
    return {"account_status": body.status}


@router.post("/users/{user_id}/verify")
async def toggle_verify_user(user_id: str, admin=Depends(require_permission("users.verify"))):
    rate_limit(f"admin-verify-user:{admin['id']}", max_attempts=60, window_seconds=300)
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    verified = not user.get("verified_identity", False)
    await db.users.update_one({"id": user_id}, {"$set": {"verified_identity": verified}})
    await log_action(admin["id"], "verify" if verified else "unverify", f"user:{user_id}")
    return {"verified_identity": verified}


# ---------- orders ----------

@router.get("/orders")
async def orders(status: Optional[str] = None, urgent: Optional[bool] = None, limit: int = 200, offset: int = 0,
                  admin=Depends(require_permission("orders.view"))):
    query: dict = {}
    if status:
        query["status"] = status
    if urgent is not None:
        query["urgent"] = urgent
    return await db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, admin=Depends(require_permission("orders.cancel"))):
    rate_limit(f"admin-cancel-order:{admin['id']}", max_attempts=30, window_seconds=600)
    # Atomic claim, same guard style used everywhere else in the order lifecycle —
    # admin can reach further into the lifecycle than a client can (fraud response
    # shouldn't be blocked by "well the client already started work"), but a
    # completed/already-cancelled/disputed order still can't be touched here.
    order = await db.orders.find_one_and_update(
        {"id": order_id, "status": {"$in": ["published", "accepted", "in_progress", "completion_requested"]}},
        {"$set": {"status": "cancelled", "cancelled_at": now()}},
    )
    if not order:
        raise HTTPException(400, "Este pedido não pode mais ser cancelado")
    if order.get("worker_id"):
        await notify(order["worker_id"], "Pedido cancelado", f"“{order['title']}” foi cancelado pela administração.", "status", order_id)
    await notify(order["client_id"], "Pedido cancelado", f"“{order['title']}” foi cancelado pela administração.", "status", order_id)
    # Reuses the exact refund pattern from the client-initiated cancel (public.py) —
    # a held payment always comes back to the client, admin cancel is no exception.
    payment = await db.payments.find_one({"order_id": order_id, "status": "held"})
    if payment:
        refund_cents = to_cents(payment["gross_amount"])
        if refund_cents > 0:
            await credit_wallet(payment["client_id"], refund_cents, "REFUND", reference_type="order", reference_id=order_id,
                                 bucket="available", description=f"Reembolso — {order['title']} (cancelado pela administração)")
        await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "refunded", "updated_at": now()}})
        await notify(payment["client_id"], "Reembolso realizado", f"O valor pago em “{order['title']}” foi devolvido para sua carteira.", "refund", order_id)
    await log_action(admin["id"], "cancel", f"order:{order_id}")
    return {"ok": True}


# ---------- catalog ----------

@router.get("/categories")
async def categories(admin=Depends(require_permission("categories.manage"))):
    cats = await db.categories.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    subs = await db.subcategories.find({}, {"_id": 0}).to_list(500)
    for c in cats:
        c["subcategories"] = [s for s in subs if s["category_id"] == c["id"]]
    return cats


@router.post("/categories")
async def create_category(body: CategoryIn, admin=Depends(require_permission("categories.manage"))):
    rate_limit(f"admin-catalog:{admin['id']}", max_attempts=60, window_seconds=300)
    order = await db.categories.count_documents({})
    cat = body.model_dump() | {"id": new_id(), "order": order}
    await db.categories.insert_one(dict(cat))
    await log_action(admin["id"], "create", f"category:{cat['id']}")
    return cat


@router.patch("/categories/{cat_id}")
async def patch_category(cat_id: str, body: ActivePatch, admin=Depends(require_permission("categories.manage"))):
    rate_limit(f"admin-catalog:{admin['id']}", max_attempts=60, window_seconds=300)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.categories.update_one({"id": cat_id}, {"$set": data})
    await log_action(admin["id"], "update", f"category:{cat_id}")
    return {"ok": True}


@router.post("/subcategories")
async def create_subcategory(body: SubcategoryIn, admin=Depends(require_permission("categories.manage"))):
    rate_limit(f"admin-catalog:{admin['id']}", max_attempts=60, window_seconds=300)
    sub = body.model_dump() | {"id": new_id()}
    await db.subcategories.insert_one(dict(sub))
    await log_action(admin["id"], "create", f"subcategory:{sub['id']}")
    return sub


@router.patch("/subcategories/{sub_id}")
async def patch_subcategory(sub_id: str, body: ActivePatch, admin=Depends(require_permission("categories.manage"))):
    rate_limit(f"admin-catalog:{admin['id']}", max_attempts=60, window_seconds=300)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.subcategories.update_one({"id": sub_id}, {"$set": data})
    await log_action(admin["id"], "update", f"subcategory:{sub_id}")
    return {"ok": True}


# ---------- geo ----------

@router.get("/geo")
async def geo(admin=Depends(require_permission("geo.manage"))):
    return {
        "states": await db.states.find({}, {"_id": 0}).to_list(50),
        "cities": await db.cities.find({}, {"_id": 0}).sort("name", 1).to_list(300),
        "neighborhoods": await db.neighborhoods.find({}, {"_id": 0}).sort("name", 1).to_list(500),
    }


@router.post("/geo/states")
async def create_state(body: GeoStateIn, admin=Depends(require_permission("geo.manage"))):
    rate_limit(f"admin-geo:{admin['id']}", max_attempts=60, window_seconds=300)
    state = body.model_dump() | {"id": new_id()}
    await db.states.insert_one(dict(state))
    await log_action(admin["id"], "create", f"state:{state['id']}")
    return state


@router.post("/geo/cities")
async def create_city(body: GeoCityIn, admin=Depends(require_permission("geo.manage"))):
    rate_limit(f"admin-geo:{admin['id']}", max_attempts=60, window_seconds=300)
    city = body.model_dump() | {"id": new_id()}
    await db.cities.insert_one(dict(city))
    await log_action(admin["id"], "create", f"city:{city['id']}")
    return city


@router.post("/geo/neighborhoods")
async def create_neighborhood(body: GeoNeighborhoodIn, admin=Depends(require_permission("geo.manage"))):
    rate_limit(f"admin-geo:{admin['id']}", max_attempts=60, window_seconds=300)
    hood = body.model_dump() | {"id": new_id()}
    await db.neighborhoods.insert_one(dict(hood))
    await log_action(admin["id"], "create", f"neighborhood:{hood['id']}")
    return hood


@router.patch("/geo/{kind}/{item_id}")
async def patch_geo(kind: str, item_id: str, body: ActivePatch, admin=Depends(require_permission("geo.manage"))):
    rate_limit(f"admin-geo:{admin['id']}", max_attempts=60, window_seconds=300)
    coll = {"states": db.states, "cities": db.cities, "neighborhoods": db.neighborhoods}.get(kind)
    if coll is None:
        raise HTTPException(400, "Tipo inválido")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await coll.update_one({"id": item_id}, {"$set": data})
    await log_action(admin["id"], "update", f"{kind}:{item_id}")
    return {"ok": True}


# ---------- reports ----------

@router.get("/reports")
async def reports(limit: int = 200, offset: int = 0, admin=Depends(require_permission("reports.view"))):
    items = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    reporter_ids = list({r["reporter_id"] for r in items})
    users = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": reporter_ids}}, {"id": 1, "name": 1})}
    return [r | {"reporter_name": users.get(r["reporter_id"], "—")} for r in items]


@router.patch("/reports/{report_id}")
async def admin_update_report(report_id: str, body: AdminReportActionIn, admin=Depends(require_permission("reports.manage"))):
    rate_limit(f"admin-update-report:{admin['id']}", max_attempts=30, window_seconds=600)
    if body.status not in ("UNDER_REVIEW", "RESOLVED", "REJECTED"):
        raise HTTPException(400, "Status inválido.")
    report = await db.reports.find_one({"id": report_id})
    if not report:
        raise HTTPException(404, "Denúncia não encontrada")
    await db.reports.update_one({"id": report_id}, {"$set": {"status": body.status, "resolution": body.resolution, "updated_at": now()}})
    await log_action(admin["id"], "update_report", f"report:{report_id}:{body.status}")
    return {"ok": True}


# ---------- risk ----------

@router.get("/risk-flags")
async def admin_list_risk_flags(status: Optional[str] = None, limit: int = 200, offset: int = 0, admin=Depends(require_permission("risk.view"))):
    query = {"status": status} if status else {}
    items = await db.risk_flags.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    user_ids = list({f["user_id"] for f in items})
    users = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": user_ids}}, {"id": 1, "name": 1})}
    return [f | {"user_name": users.get(f["user_id"], "—")} for f in items]


@router.patch("/risk-flags/{flag_id}")
async def admin_update_risk_flag(flag_id: str, body: AdminRiskFlagActionIn, admin=Depends(require_permission("risk.manage"))):
    rate_limit(f"admin-update-risk-flag:{admin['id']}", max_attempts=60, window_seconds=300)
    if body.status not in ("RESOLVED", "DISMISSED"):
        raise HTTPException(400, "Status inválido.")
    flag = await db.risk_flags.find_one({"id": flag_id})
    if not flag:
        raise HTTPException(404, "Sinalização não encontrada")
    await db.risk_flags.update_one({"id": flag_id}, {"$set": {"status": body.status, "note": body.note, "updated_at": now()}})
    await log_action(admin["id"], "update_risk_flag", f"risk_flag:{flag_id}:{body.status}")
    return {"ok": True}


# ---------- financial ----------

@router.get("/wallets/{user_id}")
async def admin_get_wallet(user_id: str, admin=Depends(require_permission("wallet.view"))):
    from wallet import get_or_create_wallet
    return wallet_public(await get_or_create_wallet(user_id))


@router.post("/wallets/{user_id}/adjust")
async def admin_adjust_wallet(user_id: str, body: AdminAdjustmentIn, admin=Depends(require_permission("wallet.adjust")),
                               idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    rate_limit(f"admin-wallet-adjust:{admin['id']}", max_attempts=300, window_seconds=600)
    if body.amount == 0:
        raise HTTPException(400, "Informe um valor diferente de zero.")
    cents = to_cents(abs(body.amount))
    if body.amount > 0:
        txn = await credit_wallet(user_id, cents, "ADJUSTMENT", reference_type="admin_adjustment", reference_id=admin["id"],
                                   description=body.reason, idempotency_key=idempotency_key)
    else:
        try:
            txn = await debit_wallet(user_id, cents, "ADJUSTMENT", reference_type="admin_adjustment", reference_id=admin["id"],
                                      description=body.reason, idempotency_key=idempotency_key)
        except InsufficientFundsError:
            raise HTTPException(400, "Saldo disponível insuficiente para esse ajuste.")
    await log_action(admin["id"], "wallet_adjustment", f"user:{user_id}:{body.amount:+.2f}:{body.reason}")
    await notify(user_id, "Ajuste na carteira", f"Um ajuste de R$ {body.amount:+.2f} foi feito na sua carteira. Motivo: {body.reason}", "adjustment")
    return txn


@router.get("/withdrawals")
async def admin_list_withdrawals(status: Optional[str] = None, admin=Depends(require_permission("withdrawals.view"))):
    query = {"status": status} if status else {}
    return await db.withdrawals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/withdrawals/{withdrawal_id}/approve")
async def admin_approve_withdrawal(withdrawal_id: str, admin=Depends(require_permission("withdrawals.manage"))):
    rate_limit(f"admin-withdrawal-action:{admin['id']}", max_attempts=30, window_seconds=600)
    # Atomic claim first — a double-click or two admins approving the same withdrawal
    # concurrently can only have one of them actually flip PENDING/REVIEW_REQUIRED ->
    # COMPLETED; the debit below only ever runs once, for whichever request wins.
    withdrawal = await db.withdrawals.find_one_and_update(
        {"id": withdrawal_id, "status": {"$in": ["PENDING", "REVIEW_REQUIRED"]}},
        {"$set": {"status": "COMPLETED", "updated_at": now()}},
    )
    if not withdrawal:
        raise HTTPException(400, "Esse saque não pode mais ser aprovado")
    # Funds are already held in the "processing" bucket since the request was made —
    # approving means they leave the wallet for good (paid out), never returning to available.
    await debit_wallet(withdrawal["user_id"], to_cents(withdrawal["amount"]), "WITHDRAWAL", reference_type="withdrawal",
                        reference_id=withdrawal_id, bucket="processing", description="Saque aprovado", count_as_spent=False)
    await notify(withdrawal["user_id"], "Saque concluído", f"Seu saque de R$ {withdrawal['amount']:.2f} foi concluído.", "withdrawal")
    await log_action(admin["id"], "approve_withdrawal", f"withdrawal:{withdrawal_id}")
    return {"ok": True, "status": "COMPLETED"}


@router.post("/withdrawals/{withdrawal_id}/reject")
async def admin_reject_withdrawal(withdrawal_id: str, body: AdminWithdrawalActionIn, admin=Depends(require_permission("withdrawals.manage"))):
    rate_limit(f"admin-withdrawal-action:{admin['id']}", max_attempts=30, window_seconds=600)
    withdrawal = await db.withdrawals.find_one_and_update(
        {"id": withdrawal_id, "status": {"$in": ["PENDING", "REVIEW_REQUIRED"]}},
        {"$set": {"status": "FAILED", "reason": body.reason, "updated_at": now()}},
    )
    if not withdrawal:
        raise HTTPException(400, "Esse saque não pode mais ser recusado")
    await move_bucket(withdrawal["user_id"], to_cents(withdrawal["amount"]), "processing", "available", "WITHDRAWAL",
                       reference_type="withdrawal", reference_id=withdrawal_id, description=f"Saque recusado: {body.reason}")
    await notify(withdrawal["user_id"], "Saque recusado", f"Seu saque de R$ {withdrawal['amount']:.2f} foi recusado. {body.reason}", "withdrawal")
    await log_action(admin["id"], "reject_withdrawal", f"withdrawal:{withdrawal_id}:{body.reason}")
    return {"ok": True, "status": "FAILED"}


@router.get("/payments")
async def admin_list_payments(limit: int = 200, offset: int = 0, admin=Depends(require_permission("payments.view"))):
    return await db.payments.find({}, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))


@router.get("/disputes")
async def admin_list_disputes(status: Optional[str] = None, limit: int = 200, offset: int = 0, admin=Depends(require_permission("disputes.view"))):
    query = {"status": status} if status else {}
    items = await db.disputes.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    reporter_ids = list({d["reporter_id"] for d in items})
    users = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": reporter_ids}}, {"id": 1, "name": 1})}
    return [d | {"reporter_name": users.get(d["reporter_id"], "—")} for d in items]


DISPUTE_STATUSES = ("UNDER_REVIEW", "WAITING_CUSTOMER", "WAITING_PROVIDER", "RESOLVED", "REJECTED", "CANCELLED")
# A resolved/rejected/cancelled dispute always releases the order back into a real
# lifecycle state — either forward (refunded -> cancelled, released -> completed)
# or back to whatever it was doing before the dispute froze it.
DISPUTE_CLOSING_STATUSES = ("RESOLVED", "REJECTED", "CANCELLED")


@router.patch("/disputes/{dispute_id}")
async def admin_resolve_dispute(dispute_id: str, body: AdminDisputeActionIn, admin=Depends(require_permission("disputes.resolve"))):
    rate_limit(f"admin-resolve-dispute:{admin['id']}", max_attempts=30, window_seconds=600)
    if body.status not in DISPUTE_STATUSES:
        raise HTTPException(400, "Status inválido.")
    if body.resolution_action not in ("refund_client", "release_worker", "none"):
        raise HTTPException(400, "Ação de resolução inválida.")
    dispute = await db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(404, "Disputa não encontrada")
    await db.disputes.update_one({"id": dispute_id}, {"$set": {"status": body.status, "resolution": body.resolution, "updated_at": now()}})

    order = await db.orders.find_one({"id": dispute["order_id"]})
    payment = await db.payments.find_one({"order_id": dispute["order_id"], "status": "held"})

    if body.status == "RESOLVED" and body.resolution_action == "refund_client" and payment:
        refund_cents = to_cents(payment["gross_amount"])
        await credit_wallet(payment["client_id"], refund_cents, "REFUND", reference_type="dispute", reference_id=dispute_id, description="Reembolso por disputa")
        await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "refunded", "updated_at": now()}})
        await notify(payment["client_id"], "Reembolso realizado", "Sua disputa foi resolvida com reembolso.", "refund")
    elif body.status == "RESOLVED" and body.resolution_action == "release_worker" and payment:
        # Mirrors the release block in public.py's complete_order almost verbatim —
        # a dispute found in the worker's favor pays out exactly like a normal completion.
        worker_cents = to_cents(payment["worker_net_amount"])
        commission_cents = to_cents(payment["commission_amount"])
        if payment.get("worker_id") and worker_cents > 0:
            await credit_wallet(payment["worker_id"], worker_cents, "EARNING", reference_type="dispute", reference_id=dispute_id, description="Disputa resolvida a favor do fazedor")
        if commission_cents > 0:
            await credit_wallet(PLATFORM_WALLET_USER_ID, commission_cents, "COMMISSION", reference_type="dispute", reference_id=dispute_id, description="Comissão — disputa")
        await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "released", "updated_at": now()}})
        if payment.get("worker_id"):
            await db.users.update_one({"id": payment["worker_id"]}, {"$inc": {"jobs_done": 1}})
            await notify(payment["worker_id"], "Disputa resolvida a seu favor", "O pagamento foi liberado para você.", "dispute")

    # Order-status resolution — only touches orders this dispute actually locked
    # (order.status == "disputed"); an order that was already completed/cancelled
    # when the dispute was opened was never locked, so there's nothing to unwind.
    if order and order.get("status") == "disputed" and body.status in DISPUTE_CLOSING_STATUSES:
        if body.status == "RESOLVED" and body.resolution_action == "refund_client":
            await db.orders.update_one({"id": order["id"]}, {"$set": {"status": "cancelled", "cancelled_at": now()}})
        elif body.status == "RESOLVED" and body.resolution_action == "release_worker":
            await db.orders.update_one({"id": order["id"]}, {"$set": {"status": "completed", "completed_at": now()}})
        else:
            # REJECTED / CANCELLED / RESOLVED-with-no-money-action: the dispute didn't
            # change anything financially, so the order resumes where it left off.
            await db.orders.update_one({"id": order["id"]}, {"$set": {"status": order.get("pre_dispute_status", "accepted")}})

    await notify(dispute["reporter_id"], "Disputa atualizada", f"Sua disputa foi marcada como {body.status.lower()}.", "dispute")
    await log_action(admin["id"], "resolve_dispute", f"dispute:{dispute_id}:{body.status}:{body.resolution_action}")
    return {"ok": True}


@router.get("/config")
async def admin_get_config(admin=Depends(require_permission("config.view"))):
    return await get_commission_config()


@router.patch("/config")
async def admin_update_config(body: CommissionConfigIn, admin=Depends(require_permission("config.manage"))):
    rate_limit(f"admin-update-config:{admin['id']}", max_attempts=20, window_seconds=600)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data:
        data["id"] = "financial"
        await db.platform_config.update_one({"id": "financial"}, {"$set": data}, upsert=True)
        await log_action(admin["id"], "update_config", f"financial:{data}")
    return await get_commission_config()


@router.get("/security-events")
async def admin_security_events(user_id: Optional[str] = None, limit: int = 200, offset: int = 0, admin=Depends(require_permission("security_events.view"))):
    query = {"user_id": user_id} if user_id else {}
    return await db.security_events.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))


# ---------- feature flags ----------

@router.get("/feature-flags")
async def admin_list_feature_flags(admin=Depends(require_permission("feature_flags.view"))):
    return await list_flags()


@router.patch("/feature-flags/{key}")
async def admin_patch_feature_flag(key: str, body: FeatureFlagPatchIn, admin=Depends(require_permission("feature_flags.manage"))):
    rate_limit(f"admin-feature-flags:{admin['id']}", max_attempts=60, window_seconds=300)
    flag = await set_flag(key, body.enabled, admin["id"])
    await log_action(admin["id"], "update_feature_flag", f"feature_flag:{key}:{body.enabled}")
    return flag


# ---------- audit ----------

@router.get("/audit")
async def audit_log(limit: int = 200, offset: int = 0, admin=Depends(require_permission("audit.view"))):
    items = await db.admin_actions.find({}, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    admin_ids = list({a["admin_id"] for a in items})
    admins = {a["id"]: a.get("name") async for a in db.admin_users.find({"id": {"$in": admin_ids}}, {"id": 1, "name": 1})}
    return [a | {"admin_name": admins.get(a["admin_id"], "—")} for a in items]


# ---------- supervision (OWNER-only oversight view) ----------

@router.get("/supervision")
async def supervision(admin=Depends(require_permission("supervision.view"))):
    from datetime import datetime, timezone

    from admin_auth import ONLINE_WINDOW_SECONDS

    members = await db.admin_users.find({}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "totp_secret_pending": 0}).sort("name", 1).to_list(200)
    now_dt = datetime.now(timezone.utc)
    for m in members:
        last = m.get("last_active_at")
        online = False
        if last:
            try:
                online = (now_dt - datetime.fromisoformat(last)).total_seconds() <= ONLINE_WINDOW_SECONDS
            except ValueError:
                online = False
        m["online"] = online

    recent_actions = await db.admin_actions.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    action_admin_ids = list({a["admin_id"] for a in recent_actions})
    action_admins = {a["id"]: a.get("name") async for a in db.admin_users.find({"id": {"$in": action_admin_ids}}, {"id": 1, "name": 1})}
    recent_actions = [a | {"admin_name": action_admins.get(a["admin_id"], "—")} for a in recent_actions]

    # All reused queries — none of this duplicates data, just reassembles counts
    # already computed individually elsewhere (overview, tickets, risk-flags) into
    # one "what needs the OWNER's attention right now" response.
    alerts = {
        "tickets_open": await db.tickets.count_documents({"status": "OPEN"}),
        "disputes_open": await db.disputes.count_documents({"status": {"$nin": ["RESOLVED", "REJECTED", "CANCELLED"]}}),
        "reports_open": await db.reports.count_documents({"status": "OPEN"}),
        "withdrawals_review": await db.withdrawals.count_documents({"status": {"$in": ["PENDING", "REVIEW_REQUIRED"]}}),
        "risk_flags_critical": await db.risk_flags.count_documents({"status": "OPEN", "level": {"$in": ["HIGH", "CRITICAL"]}}),
    }
    return {"admins": members, "recent_actions": recent_actions, "alerts": alerts}


# ---------- notifications ----------

@router.post("/notifications")
async def admin_send_notification(body: NotificationSendIn, admin=Depends(require_permission("notifications.send"))):
    rate_limit(f"admin-notifications:{admin['id']}", max_attempts=20, window_seconds=600)
    target = body.target.strip()
    query: dict
    if target == "all":
        query = {}
    elif target.startswith("user:"):
        query = {"id": target.removeprefix("user:")}
    elif target.startswith("city:"):
        query = {"city_id": target.removeprefix("city:")}
    elif target.startswith("category:"):
        pref = target.removeprefix("category:")
        if pref not in ("client", "worker", "both"):
            raise HTTPException(400, "Categoria de destinatário inválida.")
        query = {"preference": pref}
    else:
        raise HTTPException(400, "Alvo inválido.")

    recipient_ids = [u["id"] async for u in db.users.find(query, {"id": 1})]
    if not recipient_ids:
        raise HTTPException(400, "Nenhum destinatário encontrado para esse alvo.")
    for user_id in recipient_ids:
        await notify(user_id, body.title, body.body, "admin_broadcast")
    await log_action(admin["id"], "NOTIFICATION_SENT", f"target:{target}", metadata={
        "target": target, "recipient_count": len(recipient_ids), "title": body.title,
    })
    return {"ok": True, "recipient_count": len(recipient_ids)}
