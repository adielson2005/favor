"""Marketplace core: orders and everything that hangs off one (proposals, chat
messages, reviews, reports/blocks/favorites, notifications). Mirrors Mongo
`orders`/`proposals`/`messages`/`reviews`/`reports`/`blocks`/`favorites`/
`notifications` (routes/public.py, models.py's OrderCreate/ProposalCreate/
MessageCreate/ReviewCreate/ReportCreate/BlockCreate/FavoriteToggle).

Two tables here have no 1:1 Mongo collection:
- `order_photos` — orders.photos was an unbounded array of base64 blobs; broken
  out into its own table so a future move to blob storage is a column swap
  (data_b64 -> url), not a schema migration.
- `service_status_history` — new per the product spec (seção 7). Orders only
  have a flat `status` field in Mongo; the ETL seeds exactly one synthetic row
  per order (see etl/run.py) so this table exists and is queryable going
  forward, but that seed row is NOT reconstructed history.
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKey, Index, SmallInteger, Text, TIMESTAMP, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[str] = mapped_column(Text, ForeignKey("categories.id"), nullable=False)
    subcategory_id: Mapped[str | None] = mapped_column(Text, ForeignKey("subcategories.id"))
    city_id: Mapped[str] = mapped_column(Text, ForeignKey("cities.id"), nullable=False)
    neighborhood_id: Mapped[str | None] = mapped_column(Text, ForeignKey("neighborhoods.id"))
    date_label: Mapped[str | None] = mapped_column(Text)
    time_label: Mapped[str | None] = mapped_column(Text)
    budget_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    recurrence: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    client_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    accepted_amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    accepted_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    started_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    completion_requested_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    reviewed_by_client: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    reviewed_by_worker: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    external_payment_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    external_payment_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    pre_dispute_status: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("type IN ('favor','servico')", name="ck_orders_type"),
        CheckConstraint("recurrence IN ('none','weekly','biweekly','monthly')", name="ck_orders_recurrence"),
        CheckConstraint(
            "status IN ('published','accepted','in_progress','completion_requested','completed','cancelled','disputed')",
            name="ck_orders_status",
        ),
        Index("idx_orders_client_id", "client_id"),
        Index("idx_orders_worker_id", "worker_id"),
        Index("idx_orders_city_status", "city_id", "status"),
    )


class OrderPhoto(Base):
    __tablename__ = "order_photos"

    # TEXT, not autoincrement — the ETL derives a deterministic id ("{order_id}:{position}")
    # so re-running it upserts instead of duplicating (an autoincrement PK gives the
    # loader nothing to conflict on, breaking idempotency).
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    data_b64: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("order_id", "position", name="uq_order_photos_order_position"),
        Index("idx_order_photos_order_id", "order_id"),
    )


class ServiceStatusHistory(Base):
    __tablename__ = "service_status_history"

    # TEXT, deterministic — the ETL's synthesized seed row uses id="init:{order_id}"
    # so re-running never duplicates it (see OrderPhoto's docstring for why).
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_service_status_history_order_id", "order_id", "created_at"),
    )


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    eta: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','rejected','cancelled')", name="ck_proposals_status"),
        Index("idx_proposals_order_id", "order_id"),
        Index("idx_proposals_worker_id", "worker_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    # Real data has no sender_type column — system messages are just
    # sender_id='system' (routes/public.py's system_message()), same synthesized-user
    # pattern as wallets.user_id='platform' (see identity.py). The ETL inserts a
    # users.id='system' placeholder row alongside 'platform' before loading messages.
    sender_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    image_b64: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('text','image','system')", name="ck_messages_type"),
        Index("idx_messages_order_created", "order_id", "created_at"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    from_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    to_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    stars: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_reviews_stars"),
        # One review per (order, author) — matches the reviewed_by_client/reviewed_by_worker
        # flags on `orders` that already enforce this at the application layer.
        UniqueConstraint("order_id", "from_id", name="uq_reviews_order_from"),
        Index("idx_reviews_to_id", "to_id"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    reporter_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)  # polymorphic (user/order/message) — no FK
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="OPEN")
    resolution: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("target_type IN ('user','order','message')", name="ck_reports_target_type"),
        CheckConstraint("status IN ('OPEN','UNDER_REVIEW','RESOLVED','REJECTED')", name="ck_reports_status"),
        Index("idx_reports_target", "target_type", "target_id"),
    )


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    blocked_user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("user_id <> blocked_user_id", name="ck_blocks_no_self_block"),
        UniqueConstraint("user_id", "blocked_user_id", name="uq_blocks_user_blocked"),
        Index("idx_blocks_user_id", "user_id"),
    )


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "order_id", name="uq_favorites_user_order"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # open vocabulary, no CHECK
    order_id: Mapped[str | None] = mapped_column(Text, ForeignKey("orders.id"))
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_notifications_user_created", "user_id", "created_at"),
        Index(
            "idx_notifications_user_unread", "user_id",
            postgresql_where=(read == False),  # noqa: E712 — SQLAlchemy partial-index predicate, not a Python truthiness check
        ),
    )
