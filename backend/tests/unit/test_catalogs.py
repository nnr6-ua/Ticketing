"""Resolución tolerante de catálogos por defecto (HU-01, T064)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Category, Priority
from app.services.catalogs import resolve_default_category, resolve_default_priority


def _category(name: str, **overrides: object) -> Category:
    data: dict[str, object] = {"name": name, "is_active": True}
    data.update(overrides)
    return Category(**data)


def _priority(name: str, level: int, **overrides: object) -> Priority:
    data: dict[str, object] = {"name": name, "level": level, "is_active": True}
    data.update(overrides)
    return Priority(**data)


def test_prefers_active_default(db: Session) -> None:
    preferred = _category("Red", is_default=True, sort_order=10)
    db.add_all([_category("Otros", sort_order=100), preferred])
    db.commit()

    assert resolve_default_category(db).id == preferred.id


def test_falls_back_to_first_active_when_default_is_inactive(db: Session) -> None:
    inactive_default = _category("Otros", is_default=True, is_active=False, sort_order=100)
    first_active = _category("Red", sort_order=10)
    db.add_all([inactive_default, first_active, _category("Hardware", sort_order=20)])
    db.commit()

    assert resolve_default_category(db).id == first_active.id


def test_falls_back_to_system_category_when_no_custom_catalog_is_active(
    db: Session,
) -> None:
    system = _category("Sin clasificar", is_system=True, sort_order=999)
    db.add_all(
        [
            _category("Red", is_active=False, sort_order=10),
            _category("Otros", is_default=True, is_active=False, sort_order=100),
            system,
        ]
    )
    db.commit()

    assert resolve_default_category(db).id == system.id


def test_prefers_custom_priority_over_system_fallback(db: Session) -> None:
    custom = _priority("Media", 3, is_default=True)
    db.add_all([custom, _priority("Sin clasificar", 4, is_system=True, sort_order=999)])
    db.commit()

    assert resolve_default_priority(db).id == custom.id


def test_falls_back_to_system_priority_when_all_custom_are_active_false(
    db: Session,
) -> None:
    system = _priority("Sin clasificar", 4, is_system=True, sort_order=999)
    db.add_all(
        [
            _priority("Crítica", 1, is_active=False),
            _priority("Media", 3, is_default=True, is_active=False),
            system,
        ]
    )
    db.commit()

    assert resolve_default_priority(db).id == system.id


def test_raises_clear_error_when_no_catalog_is_active(db: Session) -> None:
    db.add(_category("Red", is_active=False))
    db.commit()

    with pytest.raises(ApiError) as excinfo:
        resolve_default_category(db)

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "catalog_not_configured"
