"""SQLAlchemy engine/session/declarative base for the PostgreSQL side of the
project. Most of the app still reads/writes MongoDB exclusively — see
backend/etl/README.md for how the two databases relate. The one live exception
is backend/geo_catalog_repo.py (geography/catalog tables), gated behind
GEO_CATALOG_BACKEND and only enabled in the isolated environment so far.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / os.environ.get("ENV_FILE", ".env"))


class Base(DeclarativeBase):
    pass


_engine = None


def get_engine():
    # Memoized: create_engine() builds a connection pool, so calling this per
    # request (as geo_catalog_repo.py now does) without caching would leak a
    # fresh, never-disposed pool on every call.
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL não está configurada neste ambiente.")
        _engine = create_engine(url, future=True)
    return _engine


def get_session_factory():
    return sessionmaker(bind=get_engine(), future=True)
