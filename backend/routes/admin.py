from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_admin
from database import db, new_id, now
from models import ActivePatch, CategoryIn, GeoCityIn, GeoNeighborhoodIn, GeoStateIn, SubcategoryIn

router = APIRouter(prefix="/admin")


async def log_action(admin_id: str, action: str, target: str):
    await db.admin_actions.insert_one({"id": new_id(), "admin_id": admin_id, "action": action, "target": target, "created_at": now()})


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


# ---------- audit ----------

@router.get("/audit")
async def audit_log(admin=Depends(get_current_admin)):
    items = await db.admin_actions.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    admin_ids = list({a["admin_id"] for a in items})
    admins = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": admin_ids}})}
    return [a | {"admin_name": admins.get(a["admin_id"], "—")} for a in items]
