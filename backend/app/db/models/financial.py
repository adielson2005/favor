"""Money: wallets, ledger, deposits, withdrawals, payments, disputes, risk/security
events. Mirrors Mongo `wallets`/`wallet_transactions`/`deposits`/`bank_accounts`/
`withdrawals`/`payments`/`payment_events`/`disputes`/`risk_flags`/`security_events`
verified field-by-field against `wallet.py`, `routes/wallet.py`, `routes/public.py`,
`routes/admin.py` and `fraud.py` (not assumed from `payments.py`/`fraud.py` alone —
those only define the risk-scoring and provider-abstraction logic, not the documents
themselves). Field names here intentionally do NOT follow a generic
payer/payee/amount_cents convention where the real app doesn't use one (e.g.
`payments.client_id`/`worker_id`/`gross_amount_cents`, not `payer_id`/`payee_id`/
`amount_cents`) — matching real call sites matters more than internal consistency.

Ledger rule carried over from wallet.py (never violate this in the ETL or in any
future backend code that writes here): a wallet's balance is NEVER written
directly — it only ever moves because a `wallet_transactions` row was inserted.
`wallet_transactions` and `security_events` are meant to be append-only audit
trails; once real DB roles exist (see fazum_app/fazum_admin/fazum_readonly in the
migration plan) these should get `REVOKE UPDATE, DELETE ... FROM fazum_app;` —
deferred to that hardening pass, not applied yet since this phase has no real
roles configured.

`bank_accounts.document`/`account_number` hold ciphertext produced by
bank_encryption.py (the `"enc:v1:"`-prefixed format) — `agency` and
`holder_name`/`bank_code` are plaintext in Mongo today (confirmed via
routes/wallet.py, only document/account_number ever pass through encrypt_field).
The ETL copies all of these verbatim, it never decrypts/re-encrypts.

Money fields that are float reais in Mongo (deposits.amount, withdrawals.amount,
payments.gross_amount/commission_amount/worker_net_amount, proposals.amount, etc.)
become BIGINT cents columns here — a deliberate platform-wide conversion (FASE 4
decision), not a field that already exists as cents in Mongo.
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Numeric, SmallInteger, Text, TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # user_id='platform' is the platform commission wallet — see identity.py's
    # note on the synthetic 'platform' users row the ETL must insert first.
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="BRL")
    # Three real buckets, not two — 'processing' holds funds during a pending
    # withdrawal (see wallet.py's move_bucket "available -> processing" flow).
    available_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    pending_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    processing_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    total_received_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    total_spent_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # No updated_at — real wallet documents never carry one (every mutation is a
    # bare $inc in wallet.py, none of them touch a timestamp field).


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    wallet_id: Mapped[str] = mapped_column(Text, ForeignKey("wallets.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # open vocabulary, no CHECK
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # 'available' / 'pending' / 'processing' for credit/debit, or "{from}->{to}"
    # (e.g. 'available->processing') for a move_bucket transaction — open vocab.
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[str] = mapped_column(Text, nullable=False)  # polymorphic — no FK
    provider: Mapped[str | None] = mapped_column(Text)
    provider_transaction_id: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Sparse in Mongo (only set when the caller passes one) — nullable + UNIQUE
    # reproduces that exactly, since Postgres treats multiple NULLs as non-colliding.
    idempotency_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("direction IN ('IN','OUT','MOVE')", name="ck_wallet_transactions_direction"),
        CheckConstraint("status IN ('PENDING','COMPLETED','FAILED')", name="ck_wallet_transactions_status"),
        UniqueConstraint("idempotency_key", name="uq_wallet_transactions_idempotency_key"),
        Index("idx_wallet_transactions_wallet_id", "wallet_id", "created_at"),
    )


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False, server_default="pix")
    # Real values seen: PENDING, PROCESSING, FAILED — there is no code path that
    # ever marks a deposit COMPLETED yet (no webhook/confirm handler exists today).
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    provider_transaction_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','PROCESSING','FAILED')", name="ck_deposits_status"),
        UniqueConstraint("idempotency_key", name="uq_deposits_idempotency_key"),
        Index("idx_deposits_user_id", "user_id"),
    )


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    holder_name: Mapped[str] = mapped_column(Text, nullable=False)
    document: Mapped[str] = mapped_column(Text, nullable=False)  # ciphertext ("enc:v1:...")
    bank_code: Mapped[str] = mapped_column(Text, nullable=False)
    agency: Mapped[str] = mapped_column(Text, nullable=False)  # plaintext — not encrypted in Mongo either
    account_number: Mapped[str] = mapped_column(Text, nullable=False)  # ciphertext
    account_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="checking")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_bank_accounts_user_id", "user_id"),
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bank_account_id: Mapped[str] = mapped_column(Text, ForeignKey("bank_accounts.id"), nullable=False)
    # A snapshot of the (masked) bank account at request time — routes/wallet.py's
    # mask_account(). Kept even if the bank_accounts row is later removed/changed.
    bank_account_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    risk_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)  # only set on admin rejection

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','REVIEW_REQUIRED','CANCELLED','COMPLETED','FAILED')",
            name="ck_withdrawals_status",
        ),
        CheckConstraint("risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_withdrawals_risk_level"),
        UniqueConstraint("idempotency_key", name="uq_withdrawals_idempotency_key"),
        Index("idx_withdrawals_user_id", "user_id"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    gross_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    worker_net_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # lowercase real values, see CHECK below
    provider: Mapped[str | None] = mapped_column(Text)
    provider_transaction_id: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    client_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending','held','released','refunded')", name="ck_payments_status"),
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        Index("idx_payments_client_id", "client_id"),
    )


class PaymentEvent(Base):
    """Webhook stub log (routes/wallet.py) — no live payment provider is wired in
    yet, so this table is intentionally 4 columns: it only dedupes and archives the
    raw payload, nothing more.
    """
    __tablename__ = "payment_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    reporter_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="OPEN")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("target_type IN ('service','payment','worker','client')", name="ck_disputes_target_type"),
        CheckConstraint(
            "status IN ('OPEN','UNDER_REVIEW','WAITING_CUSTOMER','WAITING_PROVIDER','RESOLVED','REJECTED','CANCELLED')",
            name="ck_disputes_status",
        ),
        Index("idx_disputes_order_id", "order_id"),
    )


class DisputeEvidence(Base):
    """disputes.evidence was an unbounded array of base64 image data-URIs in Mongo
    (routes/wallet.py's create_dispute, max ~2MB per image) — broken out into its
    own table for the exact same reason as orders.py's OrderPhoto.
    """
    __tablename__ = "dispute_evidence"

    # TEXT, deterministic ("{dispute_id}:{position}") — same idempotency reasoning
    # as orders.py's OrderPhoto.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dispute_id: Mapped[str] = mapped_column(Text, ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    data_b64: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("dispute_id", "position", name="uq_dispute_evidence_dispute_position"),
        Index("idx_dispute_evidence_dispute_id", "dispute_id"),
    )


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # open vocabulary, no CHECK
    reference_id: Mapped[str] = mapped_column(Text, nullable=False)  # polymorphic — no FK
    level: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="OPEN")
    note: Mapped[str | None] = mapped_column(Text)  # set only on admin resolution
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))  # absent until resolved

    __table_args__ = (
        CheckConstraint("level IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_risk_flags_level"),
        CheckConstraint("status IN ('OPEN','RESOLVED','DISMISSED')", name="ck_risk_flags_status"),
        Index("idx_risk_flags_user_id", "user_id"),
    )


class SecurityEvent(Base):
    """User-side security trail only (login, password/email/phone changes, Google
    link/unlink, bank account add/remove) — admin logins/2FA/session-revocation go
    to admin_actions instead (admin.py), never here (confirmed: admin_auth.py never
    touches db.security_events).
    """
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False)  # open vocabulary, no CHECK
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_security_events_user_id", "user_id", "created_at"),
    )
