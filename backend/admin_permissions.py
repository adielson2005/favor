"""Permission catalog for the admin panel's RBAC.

Every key here must be checked server-side via `require_permission()`
(admin_auth.py) — the frontend sidebar hides screens the caller can't reach,
but that's UX only, never the actual gate.
"""

PERMISSIONS = (
    "dashboard.view",
    "users.view",
    "users.block",
    "users.verify",
    "users.sessions.revoke",
    "users.status.manage",
    "orders.view",
    "orders.cancel",
    "reports.view",
    "reports.manage",
    "disputes.view",
    "disputes.resolve",
    "risk.view",
    "risk.manage",
    "wallet.view",
    "wallet.adjust",
    "withdrawals.view",
    "withdrawals.manage",
    "payments.view",
    "categories.manage",
    "geo.manage",
    "config.view",
    "config.manage",
    "feature_flags.view",
    "feature_flags.manage",
    "security_events.view",
    "audit.view",
    "admin_team.view",
    "admin_team.manage",
    "support.view",
    "support.manage",
    "feedback.view",
    "feedback.manage",
    "maintenance.view",
    "maintenance.manage",
    "notifications.send",
    "supervision.view",
)

# SUPPORT gets exactly the support-desk-shaped slice from the spec's explicit
# allow-list: view users/orders/reports/disputes, act on reports, handle tickets
# and feedback, and the non-financial user actions (block, verify identity,
# revoke sessions). Anything that touches money, config, catalog, security
# review, audit, or other admin accounts is OWNER-only by default.
#
# MANAGER runs operations one notch above SUPPORT: can manage disputes/reports,
# see (not approve) payments/withdrawals, and see security/support/maintenance
# for oversight — but never touches wallet balances, config, feature flags,
# other admin accounts, or audit logs. Least-privilege per the spec's own final
# rule: "nenhum usuário deve receber mais acesso do que necessita".
#
# MAINTENANCE is the narrowest role of all — only the technical ticket queue.
# No dashboard, no users, no financial data of any kind. `maintenance.manage`
# is further scoped to BUG-category tickets at the query level in routes/tickets.py,
# not as a separate permission key.
ROLE_PERMISSIONS = {
    "OWNER": "*",
    "MANAGER": (
        "dashboard.view",
        "users.view",
        "users.block",
        "users.verify",
        "users.sessions.revoke",
        "users.status.manage",
        "orders.view",
        "orders.cancel",
        "payments.view",
        "withdrawals.view",
        "disputes.view",
        "disputes.resolve",
        "reports.view",
        "reports.manage",
        "support.view",
        "feedback.view",
        "maintenance.view",
        "risk.view",
        "security_events.view",
    ),
    "SUPPORT": (
        "dashboard.view",
        "users.view",
        "users.block",
        "users.verify",
        "users.sessions.revoke",
        "orders.view",
        "reports.view",
        "reports.manage",
        "disputes.view",
        "support.view",
        "support.manage",
        "feedback.view",
        "feedback.manage",
    ),
    "MAINTENANCE": (
        "maintenance.view",
        "maintenance.manage",
    ),
}


def permissions_for_role(role: str) -> set[str] | str:
    """Returns "*" for full access, or a set of permission keys."""
    perms = ROLE_PERMISSIONS.get(role, ())
    return "*" if perms == "*" else set(perms)


def has_permission(granted: set[str] | str, key: str) -> bool:
    return granted == "*" or key in granted
