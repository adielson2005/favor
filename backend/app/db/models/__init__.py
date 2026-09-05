"""Imports every model module so Base.metadata is fully populated by a single
`from app.db.models import *`-style import — used by alembic/env.py (for
autogenerate) and etl/run.py (for the Table objects), so DDL and ETL can never
drift apart by referencing two different definitions of the same table.
"""
from app.db.models import admin, catalog, financial, geography, identity, orders, support  # noqa: F401
