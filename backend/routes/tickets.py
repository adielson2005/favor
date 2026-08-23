"""Support & feedback tickets — one unified funnel per the spec: a bug report, a
feature idea, a complaint, a payment question, all go through the same collection
and the same OPEN -> ... -> RESOLVED/CLOSED lifecycle, whether it's handled by
SUPPORT or handed off to MAINTENANCE (transfer_to_maintenance just recategorizes
it as BUG — MAINTENANCE never gets a separate permission, just a query-level scope
to that one category, see `_admin_ticket_query`/`_can_manage_ticket` below).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from admin_auth import require_any_permission
from auth import get_current_user, rate_limit
from database import db, new_id, now
from models import TICKET_CATEGORIES, TICKET_STATUSES, AdminTicketActionIn, TicketCreate, TicketMessageIn
from routes.admin import log_action
from routes.public import notify

router = APIRouter()


# ---------- user-facing ----------

@router.post("/tickets")
async def create_ticket(body: TicketCreate, current=Depends(get_current_user)):
    rate_limit(f"ticket-create:{current['id']}", max_attempts=20, window_seconds=600)
    if body.category not in TICKET_CATEGORIES:
        raise HTTPException(400, "Categoria inválida.")
    ticket = {
        "id": new_id(), "created_by": current["id"], "category": body.category, "subject": body.subject,
        "description": body.description, "status": "OPEN", "assigned_to": None,
        "messages": [{"id": new_id(), "author_type": "user", "author_id": current["id"], "text": body.description, "created_at": now()}],
        "created_at": now(), "updated_at": now(),
    }
    await db.tickets.insert_one(dict(ticket))
    ticket.pop("_id", None)
    return ticket


@router.get("/tickets")
async def list_my_tickets(current=Depends(get_current_user)):
    return await db.tickets.find({"created_by": current["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/tickets/{ticket_id}")
async def get_my_ticket(ticket_id: str, current=Depends(get_current_user)):
    ticket = await db.tickets.find_one({"id": ticket_id, "created_by": current["id"]}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    return ticket


@router.post("/tickets/{ticket_id}/messages")
async def reply_to_my_ticket(ticket_id: str, body: TicketMessageIn, current=Depends(get_current_user)):
    rate_limit(f"ticket-message:{current['id']}", max_attempts=60, window_seconds=600)
    ticket = await db.tickets.find_one({"id": ticket_id, "created_by": current["id"]})
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    message = {"id": new_id(), "author_type": "user", "author_id": current["id"], "text": body.text, "created_at": now()}
    # A reply from the user re-opens a resolved/waiting ticket instead of silently
    # landing in a thread nobody's actively watching anymore.
    new_status = "OPEN" if ticket["status"] in ("WAITING_USER", "RESOLVED") else ticket["status"]
    await db.tickets.update_one({"id": ticket_id}, {"$push": {"messages": message}, "$set": {"status": new_status, "updated_at": now()}})
    return {"ok": True}


# ---------- admin-facing ----------

def _admin_ticket_query(admin: dict) -> dict:
    """MAINTENANCE only ever sees BUG-category tickets — enforced at the query level,
    not as a separate permission key. OWNER/MANAGER/SUPPORT (support.view) see all."""
    granted = admin["permissions"]
    if granted == "*" or "support.view" in granted:
        return {}
    return {"category": "BUG"}


def _assert_can_manage(admin: dict, ticket: dict) -> None:
    granted = admin["permissions"]
    if granted == "*" or "support.manage" in granted:
        return
    if "maintenance.manage" in granted and ticket.get("category") == "BUG":
        return
    raise HTTPException(403, "Você não tem permissão para essa ação.")


@router.get("/admin/tickets")
async def admin_list_tickets(status: Optional[str] = None, category: Optional[str] = None, limit: int = 200, offset: int = 0,
                              admin: dict = Depends(require_any_permission("support.view", "maintenance.view"))):
    query = _admin_ticket_query(admin)
    if status:
        query["status"] = status
    if category:
        if _admin_ticket_query(admin) and category != "BUG":
            # MAINTENANCE explicitly asking for a non-BUG category — same as not
            # asking at all, the scope below still wins, just return nothing instead
            # of silently ignoring their filter.
            return {"items": [], "total": 0}
        query["category"] = category
    total = await db.tickets.count_documents(query)
    items = await db.tickets.find(query, {"_id": 0}).sort("created_at", -1).skip(max(offset, 0)).to_list(min(limit, 500))
    return {"items": items, "total": total}


@router.get("/admin/tickets/{ticket_id}")
async def admin_get_ticket(ticket_id: str, admin: dict = Depends(require_any_permission("support.view", "maintenance.view"))):
    query = {"id": ticket_id, **_admin_ticket_query(admin)}
    ticket = await db.tickets.find_one(query, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    return ticket


@router.post("/admin/tickets/{ticket_id}/messages")
async def admin_reply_to_ticket(ticket_id: str, body: TicketMessageIn,
                                 admin: dict = Depends(require_any_permission("support.manage", "maintenance.manage"))):
    rate_limit(f"admin-ticket-message:{admin['id']}", max_attempts=100, window_seconds=600)
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    _assert_can_manage(admin, ticket)
    message = {"id": new_id(), "author_type": "admin", "author_id": admin["id"], "text": body.text, "created_at": now()}
    await db.tickets.update_one({"id": ticket_id}, {"$push": {"messages": message}, "$set": {"status": "WAITING_USER", "updated_at": now()}})
    await notify(ticket["created_by"], "Resposta do suporte", f"Você recebeu uma resposta no chamado \"{ticket['subject']}\".", "ticket")
    await log_action(admin["id"], "TICKET_REPLIED", f"ticket:{ticket_id}")
    return {"ok": True}


@router.patch("/admin/tickets/{ticket_id}")
async def admin_update_ticket(ticket_id: str, body: AdminTicketActionIn,
                               admin: dict = Depends(require_any_permission("support.manage", "maintenance.manage"))):
    rate_limit(f"admin-ticket-manage:{admin['id']}", max_attempts=100, window_seconds=600)
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    _assert_can_manage(admin, ticket)

    data: dict = {}
    if body.status is not None:
        if body.status not in TICKET_STATUSES:
            raise HTTPException(400, "Status inválido.")
        data["status"] = body.status
    if body.category is not None:
        if body.category not in TICKET_CATEGORIES:
            raise HTTPException(400, "Categoria inválida.")
        data["category"] = body.category
    if body.assigned_to is not None:
        data["assigned_to"] = body.assigned_to

    transferred = False
    if body.transfer_to_maintenance:
        data["category"] = "BUG"
        data["assigned_to"] = None
        transferred = True

    if not data:
        return {"ok": True}
    data["updated_at"] = now()
    await db.tickets.update_one({"id": ticket_id}, {"$set": data})
    action = "TICKET_TRANSFERRED" if transferred else "TICKET_UPDATED"
    await log_action(admin["id"], action, f"ticket:{ticket_id}", metadata=data)
    if data.get("status") in ("RESOLVED", "CLOSED"):
        await notify(ticket["created_by"], "Chamado atualizado", f"Seu chamado \"{ticket['subject']}\" foi marcado como {data['status'].lower()}.", "ticket")
    return {"ok": True}
