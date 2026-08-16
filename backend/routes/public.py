import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, get_optional_user
from database import db, new_id, now
from models import (BlockCreate, FavoriteToggle, MessageCreate, OrderCreate,
                    ProfileUpdate, ProposalCreate, ReportCreate, ReviewCreate)

router = APIRouter()

STATUS_LABELS = {
    "published": "Recebendo propostas",
    "accepted": "Aceito",
    "in_progress": "Em andamento",
    "completed": "Concluído",
    "cancelled": "Cancelado",
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
    return {k: user.get(k) for k in ("id", "name", "initials", "bio", "rating", "rating_count", "jobs_done", "city_id", "neighborhood_id", "preference", "verified_email", "verified_phone", "verified_identity", "member_since", "is_admin")} | {"level": user_level(user)}


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
    await db.notifications.insert_one({"id": new_id(), "user_id": user_id, "title": title, "body": body, "type": kind, "order_id": order_id, "read": False, "created_at": now()})


async def system_message(order_id: str, text: str):
    await db.messages.insert_one({"id": new_id(), "order_id": order_id, "sender_id": "system", "type": "system", "text": text, "created_at": now()})


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
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data:
        await db.users.update_one({"id": user_id}, {"$set": data})
    return await get_user(user_id)


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
                      max_budget: Optional[float] = None, limit: int = 60,
                      current: Optional[dict] = Depends(get_optional_user)):
    query: dict = {}
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
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 100))
    return await enrich_orders(orders)


@router.post("/orders")
async def create_order(body: OrderCreate, current=Depends(get_current_user)):
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


@router.post("/orders/{order_id}/start")
async def start_order(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] not in (order.get("worker_id"), order["client_id"]):
        raise HTTPException(403, "Você não participa deste pedido")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": "in_progress", "started_at": now()}})
    await system_message(order_id, "O serviço está em andamento.")
    await notify(order["client_id"], "Serviço em andamento", "O fazedor começou o seu pedido.", "status", order_id)
    return {"ok": True, "status": "in_progress"}


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order["client_id"]:
        raise HTTPException(403, "Apenas quem pediu pode concluir")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": "completed", "completed_at": now()}})
    if order.get("worker_id"):
        await db.users.update_one({"id": order["worker_id"]}, {"$inc": {"jobs_done": 1}})
        await notify(order["worker_id"], "Serviço concluído", f"“{order['title']}” foi marcado como concluído.", "status", order_id)
    await system_message(order_id, "O serviço foi concluído.")
    return {"ok": True, "status": "completed"}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] != order["client_id"]:
        raise HTTPException(403, "Apenas quem pediu pode cancelar")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": "cancelled", "cancelled_at": now()}})
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
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["status"] != "published":
        raise HTTPException(400, "Este pedido não está mais recebendo propostas")
    if order["client_id"] == current["id"]:
        raise HTTPException(400, "Você não pode enviar proposta para o próprio pedido")
    if await db.proposals.find_one({"order_id": order_id, "worker_id": current["id"]}):
        raise HTTPException(400, "Você já enviou uma proposta para este pedido")
    proposal = body.model_dump() | {"id": new_id(), "order_id": order_id, "worker_id": current["id"], "status": "pending", "created_at": now()}
    await db.proposals.insert_one(dict(proposal))
    await notify(order["client_id"], "Nova proposta", f"Você recebeu uma proposta em “{order['title']}”.", "proposal", order_id)
    return proposal


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(proposal_id: str, current=Depends(get_current_user)):
    proposal = await db.proposals.find_one({"id": proposal_id}, {"_id": 0})
    if not proposal:
        raise HTTPException(404, "Proposta não encontrada")
    order = await db.orders.find_one({"id": proposal["order_id"]})
    if not order or order["client_id"] != current["id"]:
        raise HTTPException(403, "Apenas quem pediu pode aceitar propostas")
    await db.proposals.update_many({"order_id": proposal["order_id"], "id": {"$ne": proposal_id}}, {"$set": {"status": "rejected"}})
    await db.proposals.update_one({"id": proposal_id}, {"$set": {"status": "accepted"}})
    await db.orders.update_one({"id": proposal["order_id"]}, {"$set": {"status": "accepted", "worker_id": proposal["worker_id"], "accepted_amount": proposal["amount"]}})
    await system_message(proposal["order_id"], "Você aceitou a proposta.")
    await notify(proposal["worker_id"], "Proposta aceita", f"Sua proposta em “{order['title']}” foi aceita. Já podem conversar.", "accept", proposal["order_id"])
    return proposal | {"status": "accepted"}


# ---------- chat ----------

@router.get("/orders/{order_id}/messages")
async def order_messages(order_id: str, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order or current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa desta conversa")
    return await db.messages.find({"order_id": order_id}, {"_id": 0}).sort("created_at", 1).to_list(200)


@router.post("/orders/{order_id}/messages")
async def send_message(order_id: str, body: MessageCreate, current=Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa desta conversa")
    message = {"id": new_id(), "order_id": order_id, "sender_id": current["id"],
               "type": "image" if body.image_b64 else "text", "text": body.text,
               "image_b64": body.image_b64, "created_at": now()}
    await db.messages.insert_one(dict(message))
    other = order["client_id"] if current["id"] != order["client_id"] else order.get("worker_id")
    if other:
        await notify(other, "Nova mensagem", body.text[:80] or "Enviou uma imagem", "message", order_id)
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
    order = await db.orders.find_one({"id": body.order_id})
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    if order["status"] != "completed":
        raise HTTPException(400, "Avalie apenas após a conclusão")
    if current["id"] not in (order["client_id"], order.get("worker_id")):
        raise HTTPException(403, "Você não participa deste pedido")
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
    report = body.model_dump() | {"id": new_id(), "reporter_id": current["id"], "status": "open", "created_at": now()}
    await db.reports.insert_one(dict(report))
    return report


@router.post("/blocks")
async def create_block(body: BlockCreate, current=Depends(get_current_user)):
    if not await db.blocks.find_one({"user_id": current["id"], "blocked_user_id": body.blocked_user_id}):
        await db.blocks.insert_one(body.model_dump() | {"id": new_id(), "user_id": current["id"], "created_at": now()})
    return {"ok": True}


# ---------- favorites ----------

@router.post("/favorites/toggle")
async def toggle_favorite(body: FavoriteToggle, current=Depends(get_current_user)):
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
async def list_notifications(current=Depends(get_current_user)):
    items = await db.notifications.find({"user_id": current["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"user_id": current["id"], "read": False})
    return {"items": items, "unread": unread}


@router.post("/notifications/read")
async def read_notifications(current=Depends(get_current_user)):
    await db.notifications.update_many({"user_id": current["id"]}, {"$set": {"read": True}})
    return {"ok": True}
