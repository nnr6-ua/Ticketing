from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    ConfigAction,
    ConfigurationAuditEntry,
    Priority,
    SlaRule,
    Ticket,
    TicketStatus,
    User,
)


def _category(
    db: Session,
    name: str,
    *,
    is_default: bool = False,
    is_system: bool = False,
    is_active: bool = True,
) -> Category:
    category = Category(
        name=name,
        is_default=is_default,
        is_system=is_system,
        is_active=is_active,
        revision=1,
    )
    db.add(category)
    db.commit()
    return category


def test_category_name_and_keywords_are_validated(
    client: TestClient, admin_headers
) -> None:
    blank = client.post(
        "/api/v1/admin/categories",
        json={"name": "   "},
        headers=admin_headers,
    )
    assert blank.status_code == 422

    long_keyword = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red", "keywords": ["x" * 51]},
        headers=admin_headers,
    )
    assert long_keyword.status_code == 422


def test_duplicate_names_are_case_and_whitespace_insensitive(
    client: TestClient, db: Session, admin_headers
) -> None:
    _category(db, "Telefonía")

    response = client.post(
        "/api/v1/admin/categories",
        json={"name": "  telefonía  "},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_catalog_name"


def test_last_active_category_cannot_be_deactivated(
    client: TestClient, db: Session, admin_headers
) -> None:
    first = _category(db, "Red", is_default=True)

    response = client.post(
        f"/api/v1/admin/categories/{first.id}/updates",
        json={"expected_revision": first.revision, "is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "last_active_catalog_item"


def test_default_can_be_moved_before_deactivation(
    client: TestClient, db: Session, admin_headers
) -> None:
    current = _category(db, "Otros", is_default=True)
    replacement = _category(db, "Red")

    response = client.post(
        f"/api/v1/admin/categories/{current.id}/updates",
        json={
            "expected_revision": current.revision,
            "is_active": False,
            "replacement_default_id": str(replacement.id),
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is False
    db.refresh(replacement)
    assert replacement.is_default is True


def test_setting_new_default_audits_previous_default(
    client: TestClient, db: Session, admin_headers
) -> None:
    previous = _category(db, "Otros", is_default=True)
    candidate = _category(db, "Red")

    response = client.post(
        f"/api/v1/admin/categories/{candidate.id}/updates",
        json={"expected_revision": candidate.revision, "is_default": True},
        headers=admin_headers,
    )
    assert response.status_code == 200

    audit = db.scalar(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_id == previous.id,
            ConfigurationAuditEntry.action == ConfigAction.update,
        )
    )
    assert audit is not None
    assert audit.previous_values is not None
    assert audit.previous_values["is_default"] is True
    assert audit.new_values is not None
    assert audit.new_values["is_default"] is False


def test_replacement_default_is_audited_as_promoted(
    client: TestClient, db: Session, admin_headers
) -> None:
    current = _category(db, "Otros", is_default=True)
    replacement = _category(db, "Red")

    response = client.post(
        f"/api/v1/admin/categories/{current.id}/updates",
        json={
            "expected_revision": current.revision,
            "is_active": False,
            "replacement_default_id": str(replacement.id),
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    audit = db.scalar(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_id == replacement.id,
            ConfigurationAuditEntry.action == ConfigAction.set_default,
        )
    )
    assert audit is not None
    assert audit.previous_values is not None
    assert audit.previous_values["is_default"] is False
    assert audit.new_values is not None
    assert audit.new_values["is_default"] is True


def test_create_audit_has_no_previous_values_and_separate_default_promotion(
    client: TestClient, db: Session, admin_headers
) -> None:
    response = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red", "is_default": True},
        headers=admin_headers,
    )
    assert response.status_code == 201
    category_id = uuid.UUID(response.json()["id"])

    entries = db.scalars(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_id == category_id
        )
    ).all()
    create = next(entry for entry in entries if entry.action == ConfigAction.create)
    promotion = next(
        entry for entry in entries if entry.action == ConfigAction.set_default
    )

    assert create.previous_values is None
    assert create.new_values is not None
    assert create.new_values["is_default"] is False
    assert promotion.previous_values is not None
    assert promotion.previous_values["is_default"] is False
    assert promotion.new_values is not None
    assert promotion.new_values["is_default"] is True
    assert create.configuration_version_id == promotion.configuration_version_id


def test_system_category_cannot_be_modified_or_deleted(
    client: TestClient, db: Session, admin_headers
) -> None:
    system = _category(db, "Sin clasificar", is_system=True)

    updated = client.post(
        f"/api/v1/admin/categories/{system.id}/updates",
        json={"expected_revision": system.revision, "name": "Otra"},
        headers=admin_headers,
    )
    assert updated.status_code == 409
    assert updated.json()["detail"]["code"] == "system_catalog_item"

    deleted = client.post(
        f"/api/v1/admin/categories/{system.id}/deletion",
        json={"expected_revision": system.revision},
        headers=admin_headers,
    )
    assert deleted.status_code == 409
    assert deleted.json()["detail"]["code"] == "system_catalog_item"


def test_category_in_use_cannot_be_deleted(
    client: TestClient, db: Session, admin_headers
) -> None:
    category = _category(db, "Red")
    priority = Priority(name="Alta", level=2, base_hours="8.00", is_active=True)
    db.add(priority)
    db.commit()
    db.add(
        SlaRule(
            category_id=category.id,
            priority_id=priority.id,
            hours="4.00",
            configuration_version_id=uuid.UUID(
                "0f5a7f8e-4ef7-4e0d-9a1e-9f6e2e3d4c10"
            ),
            valid_from_version=1,
            created_by_id=_user(db).id,
        )
    )
    db.commit()

    response = client.post(
        f"/api/v1/admin/categories/{category.id}/deletion",
        json={"expected_revision": category.revision},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "catalog_in_use"


def test_category_deletion_creates_one_audit_entry(
    client: TestClient, db: Session, admin_headers
) -> None:
    category = _category(db, "Red")
    response = client.post(
        f"/api/v1/admin/categories/{category.id}/deletion",
        json={"expected_revision": category.revision},
        headers=admin_headers,
    )
    assert response.status_code == 200
    entries = db.scalars(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_id == category.id
        )
    ).all()
    assert len(entries) == 1
    assert entries[0].action.value == "delete"


def _user(db: Session) -> User:
    user = db.scalar(select(User).limit(1))
    if user is None:
        user = User(
            name="Admin",
            email="admin.helper@example.com",
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
    return user


def test_category_with_tickets_reports_counts(
    client: TestClient, db: Session, admin_headers
) -> None:
    category = _category(db, "Red")
    priority = Priority(name="Alta", level=2, base_hours="8.00", is_active=True)
    db.add(priority)
    db.commit()
    creator = _user(db)
    db.add(
        Ticket(
            number="TK-009001",
            title="Incidencia de prueba",
            description="Descripción de prueba para contar tickets.",
            status=TicketStatus.abierto,
            creator_id=creator.id,
            category_id=category.id,
            priority_id=priority.id,
        )
    )
    db.commit()

    response = client.get("/api/v1/admin/categories", headers=admin_headers)
    assert response.status_code == 200
    item = next(row for row in response.json() if row["id"] == str(category.id))
    assert item["ticket_count"] == 1
    assert item["can_delete"] is False


def test_category_referenced_by_ticket_cannot_be_deleted(
    client: TestClient, db: Session, admin_headers
) -> None:
    category = _category(db, "Red")
    priority = Priority(name="Alta", level=2, base_hours="8.00", is_active=True)
    db.add(priority)
    db.commit()
    creator = _user(db)
    db.add(
        Ticket(
            number="TK-009002",
            title="Incidencia referenciada",
            description="Descripción de la incidencia referenciada.",
            status=TicketStatus.abierto,
            creator_id=creator.id,
            category_id=category.id,
            priority_id=priority.id,
        )
    )
    db.commit()

    response = client.post(
        f"/api/v1/admin/categories/{category.id}/deletion",
        json={"expected_revision": category.revision},
        headers=admin_headers,
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "catalog_in_use"
    assert "Desactívala" in detail["message"]
    assert db.get(Category, category.id) is not None
