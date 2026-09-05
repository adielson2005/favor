"""Identity: users + how they authenticate. Mirrors Mongo `users`/`auth_accounts`/
`verification_tokens` (routes/auth.py, routes/public.py's public_user/private_user,
auth_accounts.py, verification.py, models.py's RegisterIn/ProfileUpdate).

Note: two synthetic rows must exist before dependent tables load (see
backend/etl/run.py): `users.id = 'platform'` (the commission wallet's owner, see
app/db/models/financial.py:Wallet) and `users.id = 'system'` (the sender of
automated chat messages, see app/db/models/orders.py:Message) — Mongo never had a
matching `users` doc for either, since both are just string constants used
directly as a `user_id`/`sender_id` value in wallet.py and routes/public.py.
"""
from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, TIMESTAMP, UniqueConstraint, desc,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)  # nullable: Google-only accounts
    initials: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    jobs_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    city_id: Mapped[str] = mapped_column(Text, ForeignKey("cities.id"), nullable=False)
    neighborhood_id: Mapped[str | None] = mapped_column(Text, ForeignKey("neighborhoods.id"))
    state_id: Mapped[str] = mapped_column(Text, ForeignKey("states.id"), nullable=False)
    preference: Mapped[str] = mapped_column(Text, nullable=False)
    verified_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_identity: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_verified_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    phone_verified_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    account_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING_VERIFICATION")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")  # legacy field, carried as-is
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    member_since: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    avatar_b64: Mapped[str | None] = mapped_column(Text)  # flagged for future blob-storage move, out of scope now
    notification_prefs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint("preference IN ('client','worker','both')", name="ck_users_preference"),
        CheckConstraint(
            "account_status IN ('PENDING_VERIFICATION','ACTIVE','SUSPENDED','BLOCKED')",
            name="ck_users_account_status",
        ),
        Index("idx_users_city_id", "city_id"),
    )


class AuthAccount(Base):
    __tablename__ = "auth_accounts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_account_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        # Real values are uppercase (auth_accounts.py's PROVIDER_PASSWORD/PROVIDER_GOOGLE
        # constants: "PASSWORD"/"GOOGLE"), not lowercase as the naming convention
        # elsewhere in this file might suggest — confirmed against faze_isolated data.
        CheckConstraint("provider IN ('PASSWORD','GOOGLE')", name="ck_auth_accounts_provider"),
        UniqueConstraint("provider", "provider_account_id", name="uq_auth_accounts_provider_account"),
        Index("idx_auth_accounts_user_id", "user_id"),
    )


class VerificationToken(Base):
    """Verified against verification.py — real shape differs a lot from a naive
    guess: the code is never stored plaintext (only its hash), 'type' has a third
    value (PASSWORD_RESET) and is uppercase, and there's an attempt-limiting and
    used/verified lifecycle beyond a bare expiry.
    """
    __tablename__ = "verification_tokens"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    verified_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('EMAIL','PHONE','PASSWORD_RESET')", name="ck_verification_tokens_type"),
        Index("idx_verification_tokens_lookup", "user_id", "type", desc("created_at")),
        Index("idx_verification_tokens_expires_at", "expires_at"),
    )
