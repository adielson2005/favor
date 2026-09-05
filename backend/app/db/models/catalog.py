"""Service catalog: categories -> subcategories. Mirrors Mongo `categories`/
`subcategories` (routes/public.py's /categories, routes/admin.py's CRUD,
models.py's CategoryIn/SubcategoryIn).
"""
from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    order: Mapped[int] = mapped_column("order", Integer, nullable=False, server_default="0")

    subcategories: Mapped[list["Subcategory"]] = relationship(back_populates="category")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    category_id: Mapped[str] = mapped_column(Text, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    category: Mapped["Category"] = relationship(back_populates="subcategories")

    __table_args__ = (
        Index("idx_subcategories_category_id", "category_id"),
    )
