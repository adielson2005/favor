"""Geography: states -> cities -> neighborhoods. Mirrors the Mongo `states`/
`cities`/`neighborhoods` collections (routes/public.py's geo endpoints,
routes/admin.py's geo CRUD, models.py's GeoStateIn/GeoCityIn/GeoNeighborhoodIn).
"""
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class State(Base):
    __tablename__ = "states"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    uf: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    cities: Mapped[list["City"]] = relationship(back_populates="state")


class City(Base):
    __tablename__ = "cities"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    state_id: Mapped[str] = mapped_column(Text, ForeignKey("states.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    state: Mapped["State"] = relationship(back_populates="cities")
    neighborhoods: Mapped[list["Neighborhood"]] = relationship(back_populates="city")

    __table_args__ = (
        Index("idx_cities_state_id", "state_id"),
    )


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    city_id: Mapped[str] = mapped_column(Text, ForeignKey("cities.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Coarse proximity grouping (e.g. "Zona Central") backing the "opportunities
    # near you" soft ranking in routes/public.py's list_orders — not geocoding,
    # just the zone labels seed.py's neighborhood list already groups by.
    zone: Mapped[str | None] = mapped_column(Text)

    city: Mapped["City"] = relationship(back_populates="neighborhoods")

    __table_args__ = (
        CheckConstraint("kind IN ('bairro','complexo','regiao','distrito','localidade')", name="ck_neighborhoods_kind"),
        Index("idx_neighborhoods_city_id", "city_id"),
    )
