"""Single source of truth for which Mongo fields are reais floats that become
BIGINT cents columns in Postgres. Shared between etl/checks.py (pre-migration
sanity pass) and etl/run.py (the actual conversion) so the two can never drift
apart and check a field the loader doesn't convert, or vice versa.

Each entry: mongo_collection -> [(mongo_field, postgres_column), ...].
"""
MONEY_FIELDS: dict[str, list[tuple[str, str]]] = {
    "deposits": [("amount", "amount_cents")],
    "withdrawals": [("amount", "amount_cents")],
    "payments": [
        ("gross_amount", "gross_amount_cents"),
        ("commission_amount", "commission_amount_cents"),
        ("worker_net_amount", "worker_net_amount_cents"),
    ],
    "proposals": [("amount", "amount_cents")],
    "orders": [("budget", "budget_cents"), ("accepted_amount", "accepted_amount_cents")],
}
