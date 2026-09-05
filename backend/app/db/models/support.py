"""Support desk: tickets and their message threads. Mirrors Mongo `tickets`,
verified field-by-field against `routes/tickets.py` and `models.py`'s
TICKET_CATEGORIES/TICKET_STATUSES constants.

`tickets.messages` was an embedded array in Mongo; here it's normalized into its
own `ticket_messages` table (per the migration plan's FASE 4 decision) so a
thread with many messages doesn't require rewriting the whole ticket document.
`ticket_messages.author_id` can be either a user or an admin_user (two different
tables) depending on `author_type` — left as plain TEXT with no FK, same
polymorphic-reference treatment as `reports.target_id`/`wallet_transactions.reference_id`.

There is no `escalated_to_maintenance` flag in the real data — "escalation" is
just `category` getting force-set to `'BUG'` (routes/tickets.py's
transfer_to_maintenance branch), which already routes the ticket into
MAINTENANCE's scope via `_admin_ticket_query`'s category filter. No `attachment_b64`
field exists on ticket messages either — only `id`/`author_type`/`author_id`/
`text`/`created_at` are ever written.
"""
from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="OPEN")
    assigned_to: Mapped[str | None] = mapped_column(Text, ForeignKey("admin_users.id"))
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('BUG','IDEIA','SUGESTAO','RECLAMACAO','PAGAMENTO','CONTA','SEGURANCA','OUTRO')",
            name="ck_tickets_category",
        ),
        CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','WAITING_USER','RESOLVED','CLOSED')", name="ck_tickets_status",
        ),
        Index("idx_tickets_created_by", "created_by"),
        Index("idx_tickets_assigned_to", "assigned_to"),
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(Text, ForeignKey("tickets.id"), nullable=False)
    author_type: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(Text, nullable=False)  # polymorphic (user or admin_user) — no FK
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("author_type IN ('user','admin')", name="ck_ticket_messages_author_type"),
        Index("idx_ticket_messages_ticket_id", "ticket_id", "created_at"),
    )
