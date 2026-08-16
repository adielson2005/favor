from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_admin
from database import db, new_id, now
from models import (
    ActivePatch, AdminAdjustmentIn, AdminDisputeActionIn, AdminWithdrawalActionIn,
    CategoryIn, CommissionConfigIn, GeoCityIn, GeoNeighborhoodIn, GeoStateIn, SubcategoryIn,
)
from wallet import (
    InsufficientFundsError, credit_wallet, debit_wallet, get_commission_config,
    move_bucket, to_cents, wallet_public,
)

router = APIRouter(prefix="/admin")


async def log_action(admin_id: str, action: str, target: str):
    await db.admin_actions.insert_one({"id": new_id(), "admin_id": admin_id, "action": action, "target": target, "created_at": now()})


async def notify(user_id: str, title: str, body: str, kind: str, order_id: Optional[str] = None):
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "title": title, "body": body, "type": kind, "order_id": order_id, "read": False, "created_at": now()})


@router.get("/overview")
async def overview(admin=Depends(get_current_admin)):
    return {
        "users": await db.users.count_documents({}),
        "orders": await db.orders.count_documents({}),
        "orders_open": await db.orders.count_documents({"status": "published"}),
        "proposals": await db.proposals.count_documents({}),
        "reviews": await db.reviews.count_documents({}),
        "reports_open": await db.reports.count_documents({"status": "open"}),
        "categories": await db.categories.count_documents({}),
        "neighborhoods": await db.neighborhoods.count_documents({}),
    }


# ---------- users ----------

@router.get("/users")
async def users(admin=Depends(get_current_admin)):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(200)


@router.post("/users/{user_id}/block")
async def toggle_block_user(user_id: str, admin=Depends(get_current_admin)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    blocked = not user.get("blocked", False)
    await db.users.update_one({"id": user_id}, {"$set": {"blocked": blocked}})
    await log_action(admin["id"], "block" if blocked else "unblock", f"user:{user_id}")
    return {"blocked": blocked}


@router.post("/users/{user_id}/verify")
async def toggle_verify_user(user_id: str, admin=Depends(get_current_admin)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    verified = not user.get("verified_identity", False)
    await db.users.update_one({"id": user_id}, {"$set": {"verified_identity": verified}})
    await log_action(admin["id"], "verify" if verified else "unverify", f"user:{user_id}")
    return {"verified_identity": verified}


# ---------- orders ----------

@router.get("/orders")
async def orders(admin=Depends(get_current_admin)):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, admin=Depends(get_current_admin)):
    await db.orders.update_one({"id": order_id}, {"$set": {"status": "cancelled"}})
    await log_action(admin["id"], "cancel", f"order:{order_id}")
    return {"ok": True}


# ---------- catalog ----------

@router.get("/categories")
async def categories(admin=Depends(get_current_admin)):
    cats = await db.categories.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    subs = await db.subcategories.find({}, {"_id": 0}).to_list(500)
    for c in cats:
        c["subcategories"] = [s for s in subs if s["category_id"] == c["id"]]
    return cats


@router.post("/categories")
async def create_category(body: CategoryIn, admin=Depends(get_current_admin)):
    order = await db.categories.count_documents({})
    cat = body.model_dump() | {"id": new_id(), "order": order}
    await db.categories.insert_one(dict(cat))
    await log_action(admin["id"], "create", f"category:{cat['id']}")
    return cat


@router.patch("/categories/{cat_id}")
async def patch_category(cat_id: str, body: ActivePatch, admin=Depends(get_current_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.categories.update_one({"id": cat_id}, {"$set": data})
    await log_action(admin["id"], "update", f"category:{cat_id}")
    return {"ok": True}


@router.post("/subcategories")
async def create_subcategory(body: SubcategoryIn, admin=Depends(get_current_admin)):
    sub = body.model_dump() | {"id": new_id()}
    await db.subcategories.insert_one(dict(sub))
    await log_action(admin["id"], "create", f"subcategory:{sub['id']}")
    return sub


@router.patch("/subcategories/{sub_id}")
async def patch_subcategory(sub_id: str, body: ActivePatch, admin=Depends(get_current_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.subcategories.update_one({"id": sub_id}, {"$set": data})
    return {"ok": True}


# ---------- geo ----------

@router.get("/geo")
async def geo(admin=Depends(get_current_admin)):
    return {
        "states": await db.states.find({}, {"_id": 0}).to_list(50),
        "cities": await db.cities.find({}, {"_id": 0}).sort("name", 1).to_list(300),
        "neighborhoods": await db.neighborhoods.find({}, {"_id": 0}).sort("name", 1).to_list(500),
    }


@router.post("/geo/states")
async def create_state(body: GeoStateIn, admin=Depends(get_current_admin)):
    state = body.model_dump() | {"id": new_id()}
    await db.states.insert_one(dict(state))
    await log_action(admin["id"], "create", f"state:{state['id']}")
    return state


@router.post("/geo/cities")
async def create_city(body: GeoCityIn, admin=Depends(get_current_admin)):
    city = body.model_dump() | {"id": new_id()}
    await db.cities.insert_one(dict(city))
    await log_action(admin["id"], "create", f"city:{city['id']}")
    return city


@router.post("/geo/neighborhoods")
async def create_neighborhood(body: GeoNeighborhoodIn, admin=Depends(get_current_admin)):
    hood = body.model_dump() | {"id": new_id()}
    await db.neighborhoods.insert_one(dict(hood))
    await log_action(admin["id"], "create", f"neighborhood:{hood['id']}")
    return hood


@router.patch("/geo/{kind}/{item_id}")
async def patch_geo(kind: str, item_id: str, body: ActivePatch, admin=Depends(get_current_admin)):
    coll = {"states": db.states, "cities": db.cities, "neighborhoods": db.neighborhoods}.get(kind)
    if coll is None:
        raise HTTPException(400, "Tipo inválido")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    await coll.update_one({"id": item_id}, {"$set": data})
    await log_action(admin["id"], "update", f"{kind}:{item_id}")
    return {"ok": True}


# ---------- reports ----------

@router.get("/reports")
async def reports(admin=Depends(get_current_admin)):
    items = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    reporter_ids = list({r["reporter_id"] for r in items})
    users = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": reporter_ids}})}
    return [r | {"reporter_name": users.get(r["reporter_id"], "—")} for r in items]


@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: str, admin=Depends(get_current_admin)):
    await db.reports.update_one({"id": report_id}, {"$set": {"status": "resolved", "resolved_at": now()}})
    await log_action(admin["id"], "resolve", f"report:{report_id}")
    return {"ok": True}


# ---------- financial ----------

@router.get("/wallets/{user_id}")
async def admin_get_wallet(user_id: str, admin=Depends(get_current_admin)):
    from wallet import get_or_create_wallet
    return wallet_public(await get_or_create_wallet(user_id))


@router.post("/wallets/{user_id}/adjust")
async def admin_adjust_wallet(user_id: str, body: AdminAdjustmentIn, admin=Depends(get_current_admin)):
    if body.amount == 0:
        raise HTTPException(400, "Informe um valor diferente de zero.")
    cents = to_cents(abs(body.amount))
    if body.amount > 0:
        txn = await credit_wallet(user_id, cents, "ADJUSTMENT", reference_type="admin_adjustment", reference_id=admin["id"], description=body.reason)
    else:
        try:
            txn = await debit_wallet(user_id, cents, "ADJUSTMENT", reference_type="admin_adjustment", reference_id=admin["id"], description=body.reason)
        except InsufficientFundsError:
            raise HTTPException(400, "Saldo disponível insuficiente para esse ajuste.")
    await log_action(admin["id"], "wallet_adjustment", f"user:{user_id}:{body.amount:+.2f}:{body.reason}")
    await notify(user_id, "Ajuste na carteira", f"Um ajuste de R$ {body.amount:+.2f} foi feito na sua carteira. Motivo: {body.reason}", "adjustment")
    return txn


@router.get("/withdrawals")
async def admin_list_withdrawals(status: Optional[str] = None, admin=Depends(get_current_admin)):
    query = {"status": status} if status else {}
    return await db.withdrawals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/withdrawals/{withdrawal_id}/approve")
async def admin_approve_withdrawal(withdrawal_id: str, admin=Depends(get_current_admin)):
    withdrawal = await db.withdrawals.find_one({"id": withdrawal_id})
    if not withdrawal:
        raise HTTPException(404, "Saque não encontrado")
    if withdrawal["status"] not in ("PENDING", "REVIEW_REQUIRED"):
        raise HTTPException(400, "Esse saque não pode mais ser aprovado")
    # Funds are already held in the "processing" bucket since the request was made —
    # approving means they leave the wallet for good (paid out), never returning to available.
    await debit_wallet(withdrawal["user_id"], to_cents(withdrawal["amount"]), "WITHDRAWAL", reference_type="withdrawal",
                        reference_id=withdrawal_id, bucket="processing", description="Saque aprovado", count_as_spent=False)
    await db.withdrawals.update_one({"id": withdrawal_id}, {"$set": {"status": "COMPLETED", "updated_at": now()}})
    await notify(withdrawal["user_id"], "Saque concluído", f"Seu saque de R$ {withdrawal['amount']:.2f} foi concluído.", "withdrawal")
    await log_action(admin["id"], "approve_withdrawal", f"withdrawal:{withdrawal_id}")
    return {"ok": True, "status": "COMPLETED"}


@router.post("/withdrawals/{withdrawal_id}/reject")
async def admin_reject_withdrawal(withdrawal_id: str, body: AdminWithdrawalActionIn, admin=Depends(get_current_admin)):
    withdrawal = await db.withdrawals.find_one({"id": withdrawal_id})
    if not withdrawal:
        raise HTTPException(404, "Saque não encontrado")
    if withdrawal["status"] not in ("PENDING", "REVIEW_REQUIRED"):
        raise HTTPException(400, "Esse saque não pode mais ser recusado")
    await move_bucket(withdrawal["user_id"], to_cents(withdrawal["amount"]), "processing", "available", "WITHDRAWAL",
                       reference_type="withdrawal", reference_id=withdrawal_id, description=f"Saque recusado: {body.reason}")
    await db.withdrawals.update_one({"id": withdrawal_id}, {"$set": {"status": "FAILED", "reason": body.reason, "updated_at": now()}})
    await notify(withdrawal["user_id"], "Saque recusado", f"Seu saque de R$ {withdrawal['amount']:.2f} foi recusado. {body.reason}", "withdrawal")
    await log_action(admin["id"], "reject_withdrawal", f"withdrawal:{withdrawal_id}:{body.reason}")
    return {"ok": True, "status": "FAILED"}


@router.get("/payments")
async def admin_list_payments(admin=Depends(get_current_admin)):
    return await db.payments.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/disputes")
async def admin_list_disputes(status: Optional[str] = None, admin=Depends(get_current_admin)):
    query = {"status": status} if status else {}
    items = await db.disputes.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    reporter_ids = list({d["reporter_id"] for d in items})
    users = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": reporter_ids}})}
    return [d | {"reporter_name": users.get(d["reporter_id"], "—")} for d in items]


@router.patch("/disputes/{dispute_id}")
async def admin_resolve_dispute(dispute_id: str, body: AdminDisputeActionIn, admin=Depends(get_current_admin)):
    if body.status not in ("UNDER_REVIEW", "RESOLVED", "CANCELLED"):
        raise HTTPException(400, "Status inválido.")
    dispute = await db.disputes.find_one({"id": dispute_id})
    if not dispute:
        raise HTTPException(404, "Disputa não encontrada")
    await db.disputes.update_one({"id": dispute_id}, {"$set": {"status": body.status, "resolution": body.resolution, "updated_at": now()}})
    if body.refund and body.status == "RESOLVED":
        payment = await db.payments.find_one({"order_id": dispute["order_id"], "status": "held"})
        if payment:
            refund_cents = to_cents(payment["gross_amount"])
            await credit_wallet(payment["client_id"], refund_cents, "REFUND", reference_type="dispute", reference_id=dispute_id, description="Reembolso por disputa")
            await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "refunded", "updated_at": now()}})
            await notify(payment["client_id"], "Reembolso realizado", "Sua disputa foi resolvida com reembolso.", "refund")
    await notify(dispute["reporter_id"], "Disputa atualizada", f"Sua disputa foi marcada como {body.status.lower()}.", "dispute")
    await log_action(admin["id"], "resolve_dispute", f"dispute:{dispute_id}:{body.status}")
    return {"ok": True}


@router.get("/config")
async def admin_get_config(admin=Depends(get_current_admin)):
    return await get_commission_config()


@router.patch("/config")
async def admin_update_config(body: CommissionConfigIn, admin=Depends(get_current_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data:
        data["id"] = "financial"
        await db.platform_config.update_one({"id": "financial"}, {"$set": data}, upsert=True)
        await log_action(admin["id"], "update_config", f"financial:{data}")
    return await get_commission_config()


# ---------- audit ----------

@router.get("/audit")
async def audit_log(admin=Depends(get_current_admin)):
    items = await db.admin_actions.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    admin_ids = list({a["admin_id"] for a in items})
    admins = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": admin_ids}})}
    return [a | {"admin_name": admins.get(a["admin_id"], "—")} for a in items]
