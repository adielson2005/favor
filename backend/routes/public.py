import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pymongo import ReturnDocument

from auth import get_current_user, get_optional_user, rate_limit, verify_password
from chat_safety import scan_message_for_external_payment
from database import db, new_id, now
from fraud import check_payment_risk, create_risk_flag
from models import (BlockCreate, FavoriteToggle, MessageCreate, OrderCreate, OrderUpdate,
                    PayOrderIn, ProfileUpdate, ProposalCreate, ReportCreate, ReviewCreate)
from wallet import (
    PLATFORM_WALLET_USER_ID, InsufficientFundsError, credit_wallet, debit_wallet,
    get_commission_config, move_bucket, to_cents, to_reais, transaction_public,
)

EXTERNAL_PAYMENT_WARNING = "Para sua segurança, mantenha pagamentos e negociações dentro do fazum."

MAX_IMAGE_B64_CHARS = 2_000_000  # ~1.4MB decoded — generous for a chat photo, cheap to reject before it hits Mongo
ALLOWED_IMAGE_PREFIXES = ("data:image/jpeg", "data:image/jpg", "data:image/png", "data:image/webp")


def validate_image_b64(value: Optional[str], field: str = "imagem"):
    if not value:
        return
    if not value.startswith(ALLOWED_IMAGE_PREFIXES):
        raise HTTPException(400, f"Formato de {field} não suportado. Use JPEG, PNG ou WebP.")
    if len(value) > MAX_IMAGE_B64_CHARS:
        raise HTTPException(400, f"Essa {field} é muito grande. Envie um arquivo menor.")

router = APIRouter()

STATUS_LABELS = {
    "published": "Recebendo propostas",
    "accepted": "Aceito",
    "in_progress": "Em andamento",
    "completion_requested": "Aguardando confirmação",
    "completed": "Concluído",
    "cancelled": "Cancelado",
    "disputed": "Em disputa",
}


def user_level(user: dict) -> str:
    if user.get("rating", 0) >= 4.8 and user.get("jobs_done", 0) >= 40:
        return "Fazedor destaque"
    if user.get("rating", 0) >= 4.5 and user.get("jobs_done", 0) >= 10:
        return "Fazedor confiável"
    if user.get("verified_identity"):
        return "Perfil verificado"
    return "Novo"


def public_user(user: Optional[dict]) -> Optional[dict]:
    if not user:
        return None
    return {k: user.get(k) for k in ("id", "name", "initials", "bio", "rating", "rating_count", "jobs_done", "city_id", "neighborhood_id", "preference", "avatar_b64", "verified_email", "verified_phone", "verified_identity", "member_since", "is_admin")} | {"level": user_level(user)}


async def ref_maps():
    cats = {c["id"]: c async for c in db.categories.find({}, {"_id": 0})}
    subs = {s["id"]: s async for s in db.subcategories.find({}, {"_id": 0})}
    hoods = {h["id"]: h async for h in db.neighborhoods.find({}, {"_id": 0})}
    cities = {c["id"]: c async for c in db.cities.find({}, {"_id": 0})}
    return cats, subs, hoods, cities


async def enrich_orders(orders: list[dict]) -> list[dict]:
    cats, subs, hoods, cities = await ref_maps()
    user_ids = {o["client_id"] for o in orders} | {o.get("worker_id") for o in orders if o.get("worker_id")}
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": list(user_ids)}}, {"_id": 0})}
    counts = {}
    order_ids = [o["id"] for o in orders]
    async for row in db.proposals.aggregate([{"$match": {"order_id": {"$in": order_ids}}}, {"$group": {"_id": "$order_id", "n": {"$sum": 1}}}]):
        counts[row["_id"]] = row["n"]
    out = []
    for o in orders:
        cat = cats.get(o.get("category_id"), {})
        hood = hoods.get(o.get("neighborhood_id"), {})
        city = cities.get(o.get("city_id"), {})
        out.append(o | {
            "category": {"id": cat.get("id"), "name": cat.get("name", "Outros"), "icon": cat.get("icon", "sparkles-outline")},
            "subcategory": (subs.get(o.get("subcategory_id")) or {}).get("name"),
            "neighborhood": hood.get("name"),
            "city": city.get("name"),
            "status_label": STATUS_LABELS.get(o.get("status"), o.get("status")),
            "client": public_user(users.get(o["client_id"])),
            "worker": public_user(users.get(o.get("worker_id"))),
            "proposals_count": counts.get(o["id"], 0),
        })
    return out


async def notify(user_id: str, title: str, body: str, kind: str, order_id: Optional[str] = None):
    user = await db.users.find_one({"id": user_id}, {"notification_prefs": 1})
    if user and (user.get("notification_prefs") or {}).get(kind) is False:
        return
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "title": title, "body": body, "type": kind, "order_id": order_id, "read": False, "created_at": now()})


async def system_message(order_id: str, text: str):
    await db.messages.insert_one({"id": new_id(), "order_id": order_id, "sender_id": "system", "type": "system", "text": text, "created_at": now()})


async def assert_not_blocked(user_a: str, user_b: str):
    if await db.blocks.find_one({"$or": [
        {"user_id": user_a, "blocked_user_id": user_b},
        {"user_id": user_b, "blocked_user_id": user_a},
    ]}):
        raise HTTPException(403, "Não é possível interagir com este usuário.")


# ---------- bootstrap / geo / catalog ----------

@router.get("/bootstrap")
async def bootstrap():
    users = await db.users.find({"is_demo": True}, {"_id": 0}).to_list(20)
    states = await db.states.find({"active": True}, {"_id": 0}).to_list(50)
    cities = await db.cities.find({"active": True}, {"_id": 0}).to_list(200)
    hoods = await db.neighborhoods.find({"active": True}, {"_id": 0}).sort("name", 1).to_list(500)
    categories = await db.categories.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    subs = await db.subcategories.find({"active": True}, {"_id": 0}).to_list(500)
    for c in categories:
        c["subcategories"] = [s for s in subs if s["category_id"] == c["id"]]
    return {"users": [public_user(u) for u in users], "states": states, "cities": cities, "neighborhoods": hoods, "categories": categories}


@router.get("/geo/states")
async def geo_states():
    return await db.states.find({"active": True}, {"_id": 0}).to_list(50)


@router.get("/geo/cities")
async def geo_cities(state_id: Optional[str] = None):
    query: dict = {"active": True}
    if state_id:
        query["state_id"] = state_id
    return await db.cities.find(query, {"_id": 0}).sort("name", 1).to_list(300)


@router.get("/geo/neighborhoods")
async def geo_neighborhoods(city_id: Optional[str] = None):
    query: dict = {"active": True}
    if city_id:
        query["city_id"] = city_id
    return await db.neighborhoods.find(query, {"_id": 0}).sort("name", 1).to_list(500)


@router.get("/categories")
async def categories():
    cats = await db.categories.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    subs = await db.subcategories.find({"active": True}, {"_id": 0}).to_list(500)
    for c in cats:
        c["subcategories"] = [s for s in subs if s["category_id"] == c["id"]]
    return cats


# ---------- users ----------

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    return public_user(user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: ProfileUpdate, current=Depends(get_current_user)):
    if current["id"] != user_id and not current.get("is_admin"):
        raise HTTPException(403, "Você só pode editar o seu próprio perfil")
    validate_image_b64(body.avatar_b64, "foto")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data:
        await db.users.update_one({"id": user_id}, {"$set": data})
    return await get_user(user_id)


@router.get("/users/{user_id}/stats")
async def user_stats(user_id: str):
    completed = await db.orders.count_documents({"worker_id": user_id, "status": "completed"})
    cancelled = await db.orders.count_documents({"worker_id": user_id, "status": "cancelled"})
    total = completed + cancelled
    return {"completion_rate": round(completed / total, 2) if total else None}


@router.get("/users/{user_id}/reviews")
async def user_reviews(user_id: str):
    reviews = await db.reviews.find({"to_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    author_ids = list({r["from_id"] for r in reviews})
    authors = {u["id"]: u async for u in db.users.find({"id": {"$in": author_ids}}, {"_id": 0})}
    return [r | {"author": public_user(authors.get(r["from_id"]))} for r in reviews]


# ---------- orders ----------

@router.get("/orders")
async def list_orders(city_id: Optional[str] = None, category_id: Optional[str] = None,
                      neighborhood_id: Optional[str] = None, type: Optional[str] = None,
                      q: Optional[str] = None, status: Optional[str] = None,
                      client_id: Optional[str] = None, worker_id: Optional[str] = None,
                      max_budget: Optional[float] = None, urgent: Optional[bool] = None,
                      limit: int = 20, offset: int = 0,
                      current: Optional[dict] = Depends(get_optional_user)):
    query: dict = {}
    if urgent is not None:
        query["urgent"] = urgent
    if city_id:
        query["city_id"] = city_id
    if category_id:
        query["category_id"] = category_id
    if neighborhood_id:
        query["neighborhood_id"] = neighborhood_id
    if type in ("favor", "servico"):
        query["type"] = type
    if status:
        query["status"] = {"$in": status.split(",")}
    elif not client_id and not worker_id:
        query["status"] = "published"
    # client_id/worker_id are "my activity" filters — always pinned to the caller's own id, never trusted from the query string.
    if client_id:
        if not current:
            raise HTTPException(401, "É preciso estar conectado.")
        query["client_id"] = current["id"]
    if worker_id:
        if not current:
            raise HTTPException(401, "É preciso estar conectado.")
        query["worker_id"] = current["id"]
    if max_budget:
        query["budget"] = {"$lte": max_budget}
    if q:
        tokens = [re.escape(t) for t in re.split(r"\W+", q, flags=re.UNICODE) if len(t) >= 3]
        pattern = "|".join(tokens) if tokens else re.escape(q)
        sub_ids = [s["id"] async for s in db.subcategories.find({"name": {"$regex": pattern, "$options": "i"}})]
        cat_ids = [c["id"] async for c in db.categories.find({"name": {"$regex": pattern, "$options": "i"}})]
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
            {"subcategory_id": {"$in": sub_ids}},
            {"category_id": {"$in": cat_ids}},
        ]
    # Kept as a plain array (not {items, total}) so every existing caller keeps working —
    # the frontend infers "more pages" by checking whether a full page came back.
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0))
    orders = await cursor.to_list(min(limit, 100))
    return await enrich_orders(orders)


@router.post("/orders")
async def create_order(body: OrderCreate, current=Depends(get_current_user)):
    rate_limit(f"create-order:{current['id']}", max_attempts=20, window_seconds=600)
    for photo in body.photos:
        validate_image_b64(photo, "foto")
    order = body.model_dump()
    order.update({"id": new_id(), "status": "published", "worker_id": None, "client_id": current["id"],
                  "reviewed_by_client": False, "reviewed_by_worker": False,
                  "is_demo": False, "created_at": now()})
    await db.orders.insert_one(dict(order))
    return (await enrich_orders([order]))[0]


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    return (await enrich_orders([order]))[0]


@router.patch("/orders/{order_id}")
async def update_order(order_id: str, body: OrderUpdate, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["client_id"] != current["id"]:
        raise HTTPException(403, "Apenas quem pediu pode editar este pedido")
    if order["status"] != "published":
        raise HTTPException(400, "Só é possível editar enquanto o pedido está recebendo propostas")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "photos" in data:
        for photo in data["photos"]:
            validate_image_b64(photo, "foto")
    if data:
        await db.orders.update_one({"id": order_id}, {"$set": data})
    return await get_order(order_id)


@router.post("/orders/{order_id}/pay")
async def pay_order(order_id: str, body: PayOrderIn, request: Request, current=Depends(get_current_user), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    rate_limit(f"pay-order:{current['id']}", max_attempts=20, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["client_id"] != current["id"]:
        raise HTTPException(403, "Apenas quem pediu pode pagar por este pedido")
    if order["status"] != "accepted":
        raise HTTPException(400, "Este pedido não está pronto para pagamento")
    if order.get("external_payment_restricted"):
        raise HTTPException(403, "Esta conversa foi restrita por possível tentativa de pagamento fora da plataforma. Fale com o suporte.")
    if body.method != "wallet":
        raise HTTPException(501, "Esse método de pagamento ainda não está disponível.")

    # The value is always recomputed here from the order's accepted proposal — the
    # request body's method choice is the only thing trusted from the frontend.
    gross_reais = order.get("accepted_amount") or order.get("budget") or 0
    if gross_reais <= 0:
        raise HTTPException(400, "Valor do pedido inválido.")
    gross_cents = to_cents(gross_reais)

    client_ip = request.client.host if request.client else None
    risk, risk_reasons = await check_payment_risk(current, gross_cents, order, client_ip=client_ip)
    if risk == "CRITICAL":
        await create_risk_flag(current["id"], "payment_attempt", order_id, risk, risk_reasons)
        raise HTTPException(403, "Este pagamento não pode ser processado agora. Fale com o suporte.")
    if risk == "HIGH":
        await create_risk_flag(current["id"], "payment", order_id, risk, risk_reasons)
    if risk == "MEDIUM":
        if not body.password:
            raise HTTPException(401, "Por segurança, confirme sua senha para concluir este pagamento.")
        if not verify_password(body.password, current.get("password_hash") or ""):
            raise HTTPException(401, "Senha incorreta.")

    config = await get_commission_config()
    commission_cents = round(gross_cents * config["commission_percent"] / 100)
    worker_net_cents = gross_cents - commission_cents

    payment = {
        "id": new_id(), "order_id": order_id, "client_id": current["id"], "worker_id": order.get("worker_id"),
        "gross_amount": to_reais(gross_cents), "commission_amount": to_reais(commission_cents),
        "worker_net_amount": to_reais(worker_net_cents), "commission_percent": config["commission_percent"],
        "method": "wallet", "status": "pending", "provider": None, "provider_transaction_id": None,
        "idempotency_key": idempotency_key, "client_ip": client_ip, "created_at": now(), "updated_at": now(),
    }
    try:
        # The unique index on payments.order_id is what actually closes the race —
        # two concurrent /pay calls for the same order can't both get past this insert,
        # so at most one ever reaches the wallet debit below.
        await db.payments.insert_one(dict(payment))
    except Exception:
        existing_payment = await db.payments.find_one({"order_id": order_id}, {"_id": 0})
        if existing_payment and idempotency_key and existing_payment.get("idempotency_key") == idempotency_key:
            return existing_payment
        raise HTTPException(400, "Este pedido já possui um pagamento")

    try:
        await debit_wallet(current["id"], gross_cents, "PAYMENT", reference_type="order", reference_id=order_id,
                            bucket="available", description=f"Pagamento — {order['title']}")
    except InsufficientFundsError:
        await db.payments.delete_one({"id": payment["id"]})
        raise HTTPException(400, "Saldo insuficiente. Deposite para continuar — outros métodos de pagamento ainda não estão disponíveis.")

    await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "held", "updated_at": now()}})
    payment["status"] = "held"
    await notify(current["id"], "Pagamento confirmado", "O valor ficará protegido até a conclusão do serviço.", "payment", order_id)
    if order.get("worker_id"):
        await notify(order["worker_id"], "Pagamento recebido", f"O cliente pagou por “{order['title']}”. Pode iniciar quando estiver pronto.", "payment", order_id)
    payment.pop("_id", None)
    return payment


@router.get("/orders/{order_id}/payment")
async def get_order_payment(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa deste pedido")
    return await db.payments.find_one({"order_id": order_id}, {"_id": 0})


@router.post("/orders/{order_id}/start")
async def start_order(order_id: str, current=Depends(get_current_user)):
    rate_limit(f"start-order:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order.get("worker_id"):
        raise HTTPException(403, "Apenas o fazedor escolhido pode iniciar o serviço")
    result = await db.orders.find_one_and_update({"id": order_id, "status": "accepted"}, {"$set": {"status": "in_progress", "started_at": now()}})
    if not result:
        raise HTTPException(400, "Este pedido não está mais aguardando início")
    await system_message(order_id, "O serviço está em andamento.")
    await notify(order["client_id"], "Serviço em andamento", "O fazedor começou o seu pedido.", "status", order_id)
    return {"ok": True, "status": "in_progress"}


@router.post("/orders/{order_id}/request-completion")
async def request_completion(order_id: str, current=Depends(get_current_user)):
    rate_limit(f"request-completion:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order.get("worker_id"):
        raise HTTPException(403, "Apenas o fazedor escolhido pode marcar como concluído")
    result = await db.orders.find_one_and_update(
        {"id": order_id, "status": "in_progress"},
        {"$set": {"status": "completion_requested", "completion_requested_at": now()}},
    )
    if not result:
        raise HTTPException(400, "Este pedido não está em andamento")
    await system_message(order_id, "O fazedor marcou o serviço como concluído. Aguardando confirmação de quem pediu.")
    await notify(order["client_id"], "Serviço concluído pelo fazedor", "Confirme para liberar o pagamento.", "status", order_id)
    return {"ok": True, "status": "completion_requested"}


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: str, current=Depends(get_current_user)):
    rate_limit(f"complete-order:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order["client_id"]:
        raise HTTPException(403, "Apenas quem pediu pode concluir")
    # Client can complete directly from in_progress (the worker signaling first via
    # /request-completion is optional, not required) or from completion_requested.
    result = await db.orders.find_one_and_update(
        {"id": order_id, "status": {"$in": ["in_progress", "completion_requested"]}},
        {"$set": {"status": "completed", "completed_at": now()}},
    )
    if not result:
        raise HTTPException(400, "Este pedido não está em andamento")
    if order.get("worker_id"):
        await db.users.update_one({"id": order["worker_id"]}, {"$inc": {"jobs_done": 1}})
        await notify(order["worker_id"], "Serviço concluído", f"“{order['title']}” foi marcado como concluído.", "status", order_id)
    # Legacy/demo orders never had a payment created for them and keep working exactly
    # as before — only orders that went through /pay have money to release here.
    payment = await db.payments.find_one({"order_id": order_id, "status": "held"})
    if payment:
        worker_cents = to_cents(payment["worker_net_amount"])
        commission_cents = to_cents(payment["commission_amount"])
        if payment.get("worker_id") and worker_cents > 0:
            await credit_wallet(payment["worker_id"], worker_cents, "EARNING", reference_type="order", reference_id=order_id,
                                 bucket="available", description=f"Ganho — {order['title']}")
        if commission_cents > 0:
            await credit_wallet(PLATFORM_WALLET_USER_ID, commission_cents, "COMMISSION", reference_type="order", reference_id=order_id,
                                 bucket="available", description=f"Comissão — {order['title']}")
        await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "released", "updated_at": now()}})
        await notify(payment["client_id"], "Pagamento liberado", f"O pagamento de “{order['title']}” foi liberado para o fazedor.", "payment", order_id)
        if payment.get("worker_id"):
            await notify(payment["worker_id"], "Novo ganho", f"Você recebeu R$ {payment['worker_net_amount']:.2f} por “{order['title']}”.", "earning", order_id)
    await system_message(order_id, "O serviço foi concluído.")
    return {"ok": True, "status": "completed"}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, current=Depends(get_current_user)):
    rate_limit(f"cancel-order:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order["client_id"]:
        raise HTTPException(403, "Apenas quem pediu pode cancelar")
    result = await db.orders.find_one_and_update({"id": order_id, "status": {"$in": ["published", "accepted"]}}, {"$set": {"status": "cancelled", "cancelled_at": now()}})
    if not result:
        raise HTTPException(400, "Este pedido não pode mais ser cancelado")
    if order.get("worker_id"):
        await notify(order["worker_id"], "Pedido cancelado", f"“{order['title']}” foi cancelado por quem pediu.", "status", order_id)
    payment = await db.payments.find_one({"order_id": order_id, "status": "held"})
    if payment:
        refund_cents = to_cents(payment["gross_amount"])
        if refund_cents > 0:
            await credit_wallet(payment["client_id"], refund_cents, "REFUND", reference_type="order", reference_id=order_id,
                                 bucket="available", description=f"Reembolso — {order['title']}")
        await db.payments.update_one({"id": payment["id"]}, {"$set": {"status": "refunded", "updated_at": now()}})
        await notify(payment["client_id"], "Reembolso realizado", f"O valor pago em “{order['title']}” foi devolvido para sua carteira.", "refund", order_id)
    return {"ok": True, "status": "cancelled"}


# ---------- proposals ----------

@router.get("/orders/{order_id}/proposals")
async def order_proposals(order_id: str):
    proposals = await db.proposals.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    worker_ids = list({p["worker_id"] for p in proposals})
    workers = {u["id"]: u async for u in db.users.find({"id": {"$in": worker_ids}}, {"_id": 0})}
    return [p | {"worker": public_user(workers.get(p["worker_id"]))} for p in proposals]


@router.post("/orders/{order_id}/proposals")
async def create_proposal(order_id: str, body: ProposalCreate, current=Depends(get_current_user)):
    rate_limit(f"create-proposal:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["status"] != "published":
        raise HTTPException(400, "Este pedido não está mais recebendo propostas")
    if order["client_id"] == current["id"]:
        raise HTTPException(400, "Você não pode enviar proposta para o próprio pedido")
    await assert_not_blocked(current["id"], order["client_id"])
    if await db.proposals.find_one({"order_id": order_id, "worker_id": current["id"]}):
        raise HTTPException(400, "Você já enviou uma proposta para este pedido")
    proposal = body.model_dump() | {"id": new_id(), "order_id": order_id, "worker_id": current["id"], "status": "pending", "created_at": now()}
    await db.proposals.insert_one(dict(proposal))
    await notify(order["client_id"], "Nova proposta", f"Você recebeu uma proposta em “{order['title']}”.", "proposal", order_id)
    return proposal


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(proposal_id: str, current=Depends(get_current_user)):
    rate_limit(f"accept-proposal:{current['id']}", max_attempts=30, window_seconds=600)
    proposal = await db.proposals.find_one({"id": proposal_id}, {"_id": 0})
    if not proposal:
        raise HTTPException(404, "Proposta não encontrada")
    order = await db.orders.find_one({"id": proposal["order_id"]})
    if not order or order["client_id"] != current["id"]:
        raise HTTPException(403, "Apenas quem pediu pode aceitar propostas")
    if proposal["status"] != "pending":
        raise HTTPException(400, "Esta proposta não está mais disponível")
    if order.get("external_payment_restricted"):
        raise HTTPException(403, "Esta conversa foi restrita por possível tentativa de pagamento fora da plataforma. Fale com o suporte.")
    # Atomic claim on the order: only succeeds while it's still published, so a double
    # tap or two near-simultaneous accepts can't both go through and clobber worker_id.
    claimed = await db.orders.find_one_and_update(
        {"id": proposal["order_id"], "status": "published"},
        {"$set": {"status": "accepted", "worker_id": proposal["worker_id"], "accepted_amount": proposal["amount"]}},
    )
    if not claimed:
        raise HTTPException(400, "Este pedido já teve uma proposta aceita.")
    other_proposals = await db.proposals.find({"order_id": proposal["order_id"], "id": {"$ne": proposal_id}}, {"_id": 0, "worker_id": 1}).to_list(100)
    await db.proposals.update_many({"order_id": proposal["order_id"], "id": {"$ne": proposal_id}}, {"$set": {"status": "rejected"}})
    await db.proposals.update_one({"id": proposal_id}, {"$set": {"status": "accepted"}})
    await system_message(proposal["order_id"], "Você aceitou a proposta.")
    await notify(proposal["worker_id"], "Proposta aceita", f"Sua proposta em “{order['title']}” foi aceita. Já podem conversar.", "accept", proposal["order_id"])
    for other in other_proposals:
        await notify(other["worker_id"], "Proposta não aceita", f"Outra proposta foi escolhida para “{order['title']}”.", "reject", proposal["order_id"])
    return proposal | {"status": "accepted"}


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_proposal(proposal_id: str, current=Depends(get_current_user)):
    rate_limit(f"cancel-proposal:{current['id']}", max_attempts=30, window_seconds=600)
    proposal = await db.proposals.find_one({"id": proposal_id})
    if not proposal:
        raise HTTPException(404, "Proposta não encontrada")
    if proposal["worker_id"] != current["id"]:
        raise HTTPException(403, "Você só pode cancelar sua própria proposta")
    # Atomic guard: only a still-pending proposal can be withdrawn — once an order's
    # been decided, losing proposals are already "rejected" and the winner "accepted".
    claimed = await db.proposals.find_one_and_update(
        {"id": proposal_id, "status": "pending"},
        {"$set": {"status": "cancelled"}},
    )
    if not claimed:
        raise HTTPException(400, "Esta proposta não pode mais ser cancelada")
    return {"ok": True, "status": "cancelled"}


# ---------- chat ----------

@router.get("/orders/{order_id}/messages")
async def order_messages(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order or current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa desta conversa")
    return await db.messages.find({"order_id": order_id}, {"_id": 0}).sort("created_at", 1).to_list(200)


@router.post("/orders/{order_id}/messages")
async def send_message(order_id: str, body: MessageCreate, current=Depends(get_current_user)):
    rate_limit(f"send-message:{current['id']}", max_attempts=120, window_seconds=300)
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa desta conversa")
    counterpart = order["worker_id"] if current["id"] == order["client_id"] else order["client_id"]
    if counterpart:
        await assert_not_blocked(current["id"], counterpart)
    validate_image_b64(body.image_b64)

    # Non-blocking external-payment detection — never censors the message itself,
    # only escalates what happens around it as the same category repeats.
    warning = None
    categories = scan_message_for_external_payment(body.text)
    if categories:
        updated_order = await db.orders.find_one_and_update(
            {"id": order_id},
            {"$inc": {f"external_payment_flags.{c}": 1 for c in categories}},
            return_document=ReturnDocument.AFTER,
        )
        flags = (updated_order or {}).get("external_payment_flags") or {}
        max_count = max((flags.get(c, 0) for c in categories), default=0)
        distinct_categories = len(flags)
        warning = EXTERNAL_PAYMENT_WARNING
        if max_count >= 6:
            await db.orders.update_one({"id": order_id}, {"$set": {"external_payment_restricted": True}})
            await create_risk_flag(current["id"], "chat_external_payment", order_id, "CRITICAL", categories)
            warning = "Esta conversa foi restrita por possível tentativa de pagamento fora da plataforma. Fale com o suporte."
        elif max_count >= 4 or distinct_categories >= 3:
            rate_limit(f"send-message-flagged:{order_id}", max_attempts=5, window_seconds=600)
            await create_risk_flag(current["id"], "chat_external_payment", order_id, "HIGH", categories)
        elif max_count >= 2:
            await system_message(order_id, "Mensagens contendo dados de pagamento externo foram detectadas. Pagamentos fora do fazum não têm proteção.")
            await create_risk_flag(current["id"], "chat_external_payment", order_id, "MEDIUM", categories)

    message = {"id": new_id(), "order_id": order_id, "sender_id": current["id"],
               "type": "image" if body.image_b64 else "text", "text": body.text,
               "image_b64": body.image_b64, "created_at": now()}
    await db.messages.insert_one(dict(message))
    other = order["client_id"] if current["id"] != order["client_id"] else order.get("worker_id")
    if other:
        await notify(other, "Nova mensagem", body.text[:80] or "Enviou uma imagem", "message", order_id)
    if warning:
        message["warning"] = warning
    return message


@router.get("/conversations")
async def conversations(current=Depends(get_current_user)):
    user_id = current["id"]
    query = {"$or": [{"client_id": user_id}, {"worker_id": user_id}], "status": {"$in": ["accepted", "in_progress", "completed"]}, "worker_id": {"$ne": None}}
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    enriched = await enrich_orders(orders)
    out = []
    for o in enriched:
        last = await db.messages.find({"order_id": o["id"]}, {"_id": 0}).sort("created_at", -1).to_list(1)
        other = o["worker"] if o["client_id"] == user_id else o["client"]
        out.append({"order": o, "other": other, "last_message": last[0] if last else None})
    return out


# ---------- reviews ----------

@router.post("/reviews")
async def create_review(body: ReviewCreate, current=Depends(get_current_user)):
    rate_limit(f"create-review:{current['id']}", max_attempts=30, window_seconds=600)
    order = await db.orders.find_one({"id": body.order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["status"] != "completed":
        raise HTTPException(400, "Avalie apenas após a conclusão")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa deste pedido")
    # The reviewer can only rate the other participant of THIS order — not an arbitrary user id.
    expected_target = order.get("worker_id") if current["id"] == order["client_id"] else order["client_id"]
    if body.to_id != expected_target:
        raise HTTPException(400, "Você só pode avaliar quem participou deste pedido com você")
    flag = "reviewed_by_client" if current["id"] == order["client_id"] else "reviewed_by_worker"
    if order.get(flag):
        raise HTTPException(400, "Você já avaliou este pedido")
    review = body.model_dump() | {"id": new_id(), "from_id": current["id"], "created_at": now()}
    await db.reviews.insert_one(dict(review))
    await db.orders.update_one({"id": body.order_id}, {"$set": {flag: True}})
    target = await db.users.find_one({"id": body.to_id})
    if target:
        count = target.get("rating_count", 0)
        new_rating = round(((target.get("rating", 5) * count) + body.stars) / (count + 1), 2)
        await db.users.update_one({"id": body.to_id}, {"$set": {"rating": new_rating, "rating_count": count + 1}})
    await notify(body.to_id, "Nova avaliação", f"Você recebeu {body.stars} estrelas.", "review", body.order_id)
    return review


# ---------- trust & safety ----------

@router.post("/reports")
async def create_report(body: ReportCreate, current=Depends(get_current_user)):
    rate_limit(f"create-report:{current['id']}", max_attempts=20, window_seconds=600)
    report = body.model_dump() | {"id": new_id(), "reporter_id": current["id"], "status": "OPEN", "created_at": now()}
    await db.reports.insert_one(dict(report))
    return report


@router.post("/blocks")
async def create_block(body: BlockCreate, current=Depends(get_current_user)):
    rate_limit(f"create-block:{current['id']}", max_attempts=30, window_seconds=600)
    if body.blocked_user_id == current["id"]:
        raise HTTPException(400, "Você não pode bloquear a si mesmo")
    if not await db.blocks.find_one({"user_id": current["id"], "blocked_user_id": body.blocked_user_id}):
        await db.blocks.insert_one(body.model_dump() | {"id": new_id(), "user_id": current["id"], "created_at": now()})
    return {"ok": True}


@router.get("/blocks")
async def list_blocks(current=Depends(get_current_user)):
    blocks = await db.blocks.find({"user_id": current["id"]}, {"_id": 0}).to_list(200)
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": [b["blocked_user_id"] for b in blocks]}}, {"_id": 0})}
    return [b | {"user": public_user(users.get(b["blocked_user_id"]))} for b in blocks]


@router.delete("/blocks/{blocked_user_id}")
async def delete_block(blocked_user_id: str, current=Depends(get_current_user)):
    await db.blocks.delete_one({"user_id": current["id"], "blocked_user_id": blocked_user_id})
    return {"ok": True}


# ---------- favorites ----------

@router.post("/favorites/toggle")
async def toggle_favorite(body: FavoriteToggle, current=Depends(get_current_user)):
    rate_limit(f"toggle-favorite:{current['id']}", max_attempts=60, window_seconds=300)
    existing = await db.favorites.find_one({"user_id": current["id"], "order_id": body.order_id})
    if existing:
        await db.favorites.delete_one({"_id": existing["_id"]})
        return {"favorited": False}
    await db.favorites.insert_one(body.model_dump() | {"id": new_id(), "user_id": current["id"], "created_at": now()})
    return {"favorited": True}


@router.get("/favorites")
async def list_favorites(current=Depends(get_current_user)):
    favs = await db.favorites.find({"user_id": current["id"]}, {"_id": 0}).to_list(100)
    order_ids = [f["order_id"] for f in favs]
    orders = await db.orders.find({"id": {"$in": order_ids}}, {"_id": 0}).to_list(100)
    return {"order_ids": order_ids, "orders": await enrich_orders(orders)}


# ---------- notifications ----------

@router.get("/notifications")
async def list_notifications(limit: int = 50, offset: int = 0, current=Depends(get_current_user)):
    items = await db.notifications.find({"user_id": current["id"]}, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 100))
    unread = await db.notifications.count_documents({"user_id": current["id"], "read": False})
    return {"items": items, "unread": unread}


@router.post("/notifications/read")
async def read_notifications(current=Depends(get_current_user)):
    rate_limit(f"read-notifications:{current['id']}", max_attempts=60, window_seconds=300)
    await db.notifications.update_many({"user_id": current["id"]}, {"$set": {"read": True}})
    return {"ok": True}
