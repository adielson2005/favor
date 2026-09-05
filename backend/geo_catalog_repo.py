"""Sync PostgreSQL repo for the geography/catalog proof-of-concept cutover slice
(states/cities/neighborhoods/categories/subcategories) — the one part of the app
that can actually read/write Postgres today, gated by GEO_CATALOG_BACKEND (default
"mongo", set to "postgres" only in backend/.env.isolated). Every function here is
plain sync SQLAlchemy; callers (routes) decide to run it via
fastapi.concurrency.run_in_threadpool so the event loop never blocks. Rows come
back as plain dicts — same shape callers already get from Mongo — so route code
doesn't need to know which backend answered.

Every write wraps IntegrityError as a clean 400: Postgres enforces constraints
(unique UF, a fixed set of neighborhood "kind" values) that Mongo never did, and
a client hitting one of those should get a normal validation error, not a 500.
"""
import os
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.base import get_session_factory
from app.db.models.catalog import Category, Subcategory
from app.db.models.geography import City, Neighborhood, State

GEO_CATALOG_BACKEND = os.environ.get("GEO_CATALOG_BACKEND", "mongo")


def _row_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _session():
    if GEO_CATALOG_BACKEND != "postgres":
        raise RuntimeError(
            "geo_catalog_repo chamado com GEO_CATALOG_BACKEND != 'postgres' — "
            "todo call site deve checar a flag antes de chamar o repo."
        )
    return get_session_factory()()


# ---------- reads ----------

def list_states(active_only: bool = True) -> list[dict]:
    with _session() as session:
        stmt = select(State)
        if active_only:
            stmt = stmt.where(State.active.is_(True))
        return [_row_to_dict(s) for s in session.execute(stmt).scalars().all()]


def list_cities(state_id: Optional[str] = None, active_only: bool = True) -> list[dict]:
    with _session() as session:
        stmt = select(City)
        if active_only:
            stmt = stmt.where(City.active.is_(True))
        if state_id:
            stmt = stmt.where(City.state_id == state_id)
        stmt = stmt.order_by(City.name)
        return [_row_to_dict(c) for c in session.execute(stmt).scalars().all()]


def list_neighborhoods(city_id: Optional[str] = None, active_only: bool = True) -> list[dict]:
    with _session() as session:
        stmt = select(Neighborhood)
        if active_only:
            stmt = stmt.where(Neighborhood.active.is_(True))
        if city_id:
            stmt = stmt.where(Neighborhood.city_id == city_id)
        stmt = stmt.order_by(Neighborhood.name)
        return [_row_to_dict(n) for n in session.execute(stmt).scalars().all()]


def get_city(city_id: str) -> Optional[dict]:
    with _session() as session:
        city = session.get(City, city_id)
        return _row_to_dict(city) if city else None


def list_categories_with_subs(active_only: bool = True) -> list[dict]:
    with _session() as session:
        cat_stmt = select(Category)
        sub_stmt = select(Subcategory)
        if active_only:
            cat_stmt = cat_stmt.where(Category.active.is_(True))
            sub_stmt = sub_stmt.where(Subcategory.active.is_(True))
        cat_stmt = cat_stmt.order_by(Category.order)
        cats = [_row_to_dict(c) for c in session.execute(cat_stmt).scalars().all()]
        subs = [_row_to_dict(s) for s in session.execute(sub_stmt).scalars().all()]
        for c in cats:
            c["subcategories"] = [s for s in subs if s["category_id"] == c["id"]]
        return cats


def load_ref_maps() -> tuple[dict, dict, dict, dict]:
    """One session, four queries, no active filter — mirrors routes/public.py's
    ref_maps() exactly (it hydrates orders regardless of whether the referenced
    category/neighborhood/city is still active)."""
    with _session() as session:
        cats = {c["id"]: c for c in (_row_to_dict(r) for r in session.execute(select(Category)).scalars().all())}
        subs = {s["id"]: s for s in (_row_to_dict(r) for r in session.execute(select(Subcategory)).scalars().all())}
        hoods = {h["id"]: h for h in (_row_to_dict(r) for r in session.execute(select(Neighborhood)).scalars().all())}
        cities = {c["id"]: c for c in (_row_to_dict(r) for r in session.execute(select(City)).scalars().all())}
        return cats, subs, hoods, cities


# ---------- writes ----------

def create_category(data: dict) -> dict:
    with _session() as session:
        order = session.execute(select(Category)).scalars().all()
        cat = Category(**data, order=len(order))
        session.add(cat)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível criar a categoria.") from e
        return _row_to_dict(cat)


def patch_category(cat_id: str, data: dict) -> None:
    _patch(Category, cat_id, data)


def create_subcategory(data: dict) -> dict:
    with _session() as session:
        sub = Subcategory(**data)
        session.add(sub)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível criar a subcategoria.") from e
        return _row_to_dict(sub)


def patch_subcategory(sub_id: str, data: dict) -> None:
    _patch(Subcategory, sub_id, data)


def create_state(data: dict) -> dict:
    with _session() as session:
        state = State(**data)
        session.add(state)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível criar o estado — UF já existe?") from e
        return _row_to_dict(state)


def create_city(data: dict) -> dict:
    with _session() as session:
        city = City(**data)
        session.add(city)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível criar a cidade.") from e
        return _row_to_dict(city)


def create_neighborhood(data: dict) -> dict:
    with _session() as session:
        hood = Neighborhood(**data)
        session.add(hood)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível criar o bairro — kind inválido?") from e
        return _row_to_dict(hood)


_GEO_MODELS = {"states": State, "cities": City, "neighborhoods": Neighborhood}


def patch_geo(kind: str, item_id: str, data: dict) -> None:
    model_cls = _GEO_MODELS.get(kind)
    if model_cls is None:
        raise HTTPException(400, "Tipo inválido")
    _patch(model_cls, item_id, data)


def _patch(model_cls, item_id: str, data: dict) -> None:
    columns = model_cls.__table__.columns.keys()
    with _session() as session:
        obj = session.get(model_cls, item_id)
        if obj is None:
            return
        for k, v in data.items():
            if k in columns:
                setattr(obj, k, v)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(400, "Não foi possível salvar — valor inválido ou duplicado.") from e
