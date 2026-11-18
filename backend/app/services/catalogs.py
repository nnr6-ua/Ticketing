from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Category, Priority


def _resolve_default(db: Session, model: type[Category] | type[Priority], label: str):
    entity = db.scalar(
        select(model)
        .where(
            model.is_active.is_(True),
            model.is_default.is_(True),
            model.is_system.is_(False),
        )
        .order_by(model.sort_order, model.id)
        .limit(1)
    )
    if entity is None:
        entity = db.scalar(
            select(model)
            .where(model.is_active.is_(True), model.is_system.is_(False))
            .order_by(model.sort_order, model.id)
            .limit(1)
        )
    if entity is None:
        entity = db.scalar(
            select(model)
            .where(model.is_active.is_(True), model.is_system.is_(True))
            .order_by(model.sort_order, model.id)
            .limit(1)
        )
    if entity is None:
        raise ApiError(
            500,
            "catalog_not_configured",
            f"No hay {label} activos configurados.",
        )
    return entity


def resolve_default_category(db: Session) -> Category:
    return _resolve_default(db, Category, "categorías")


def resolve_default_priority(db: Session) -> Priority:
    return _resolve_default(db, Priority, "prioridades")
