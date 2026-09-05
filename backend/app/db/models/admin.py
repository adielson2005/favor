"""Platform administration: admin accounts/roles, the immutable audit trail,
feature flags, system settings. Mirrors Mongo `admin_users`/`admin_roles`/
`admin_actions`/`feature_flags`/`platform_config`, verified field-by-field against
`routes/admin_auth.py`, `routes/admin.py`'s `log_action()`, `seed.py`, and
`feature_flags.py` — not assumed from the product spec's audit-log field list
(seção 27), which names fields (`resource_type`/`resource_id`/`role`/`user_agent`)
the real `log_action()` never actually writes.

`admin_roles` is a label table only — actual permission grants per role
(OWNER="*", MANAGER/SUPPORT/MAINTENANCE's granular lists) stay in
admin_permissions.py as Python code, not a ROLE_PERMISSIONS table. Per the
migration plan's FASE 4 decision: 4 fixed roles don't justify a join on every
permission check for a solo-maintained app; revisit only if roles become
runtime-configurable. Mongo's own primary key for this collection is `key`, not
`id` (seed.py) — the ETL renames it to `id` on load, same treatment as
`feature_flags.key`.

`admin_actions` is the audit log required by the product spec (seção 27) —
append-only, never editable by a regular admin. Real shape is flatter than the
spec's field list: `log_action()` (routes/admin.py) writes id/admin_id/action/
target/ip/result/metadata/created_at only — no `role` snapshot, no `resource_type`/
`resource_id` split (just one polymorphic `target` string like "admin:<id>" or
"user:<id>"), no `user_agent`, no `reason` (extra context goes in `metadata`
instead). Same deferred-REVOKE note as wallet_transactions/security_events in
financial.py applies here.

`admin_users.totp_secret`/`totp_secret_pending` hold ciphertext post-fix (task
#73, bank_encryption.py-style) — the ETL copies them verbatim, same as
bank_accounts fields in financial.py.

`system_settings` replaces the Mongo `platform_config` collection (documents keyed
by `id`, e.g. `id="financial"` holding commission_percent/min_withdrawal/etc. as
top-level fields) with a key/value table (FASE 4 decision) — the ETL nests each
document's non-id fields into `value` JSONB. `updated_by`/`updated_at` are always
NULL from the ETL (platform_config never recorded who/when), populated only by
future admin-panel writes.
"""
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminRole(Base):
    __tablename__ = "admin_roles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Mongo's `key`
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(Text)  # ciphertext ("enc:v1:...")
    totp_secret_pending: Mapped[str | None] = mapped_column(Text)  # ciphertext
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Bumped on logout/2FA-disable/deactivation/session-revocation to invalidate
    # every issued JWT at once — same pattern as users.token_version.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_login_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    last_active_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))  # presence heartbeat
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('OWNER','MANAGER','SUPPORT','MAINTENANCE')", name="ck_admin_users_role"),
    )


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    admin_id: Mapped[str] = mapped_column(Text, ForeignKey("admin_users.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # open vocabulary, no CHECK
    target: Mapped[str | None] = mapped_column(Text)  # polymorphic (e.g. "user:<id>") — no FK
    result: Mapped[str] = mapped_column(Text, nullable=False, server_default="success")
    ip: Mapped[str | None] = mapped_column(INET)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_admin_actions_admin_id", "admin_id", "created_at"),
        Index("idx_admin_actions_target", "target"),
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Mongo's `key`, e.g. "GOOGLE_LOGIN"
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text, ForeignKey("admin_users.id"))
    updated_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))  # absent until first admin edit


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Mongo platform_config's `id`, e.g. "financial"
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(Text, ForeignKey("admin_users.id"))
    updated_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
