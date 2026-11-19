from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    ConfigAction,
    ConfigurationAuditEntry,
    ConfigurationVersion,
    Priority,
    SlaRule,
    Ticket,
    User,
    UserRole,
)


def _catalog(db: Session):
    red = Category(name="Red", is_active=True, revision=1)
    inactive = Category(name="Archivada", is_active=False, revision=1)
    alta = Priority(name="Alta", level=2, base_hours="8.00", is_active=True)
    media = Priority(name="Media", level=3, base_hours="24.00", is_active=True)
    user = User(
        id=uuid.uuid4(),
        name="Solicitante",
        email="solicitante.matrix@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    db.add_all([red, inactive, alta, media, user])
    db.commit()
    return red, inactive, alta, media, user


def _upsert(category: Category, priority: Priority, hours: str, expected=None):
    return {
        "operation": "upsert",
        "category_id": str(category.id),
        "priority_id": str(priority.id),
        "hours": hours,
        "expected_rule_id": expected,
    }


def test_rule_prevails_and_retirement_falls_back_to_base(
    client: TestClient, db: Session, admin_headers, auth
) -> None:
    red, _, alta, _, user = _catalog(db)
    tech = User(
        id=uuid.uuid4(),
        name="Técnica",
        email="tecnica.retiro@example.com",
        role=UserRole.tecnico,
        is_active=True,
    )
    db.add(tech)
    db.commit()

    created = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "2.50")]},
        headers=admin_headers,
    )
    assert created.status_code == 200
    rule_id = created.json()["items"][0]["id"]

    first = client.post(
        "/api/v1/tickets",
        data={
            "title": "No funciona la VPN",
            "description": "No puedo conectar desde ayer por la tarde.",
            "priority_id": str(alta.id),
        },
        headers=auth(user),
    )
    assert first.status_code == 201
    assert first.json()["sla_hours_applied"] == "2.50"
    first_body = first.json()
    first_id = uuid.UUID(first_body["id"])
    ticket = db.get(Ticket, first_id)
    assert ticket is not None
    ticket.assignee_id = tech.id
    db.commit()
    before = next(
        item
        for item in client.get(
            "/api/v1/me/work-queue", headers=auth(tech)
        ).json()["items"]
        if item["id"] == str(first_id)
    )["sla"]

    retired = client.post(
        f"/api/v1/admin/sla-rules/{rule_id}/retirement",
        json={"expected_rule_id": rule_id},
        headers=admin_headers,
    )
    assert retired.status_code == 200
    assert retired.json()["items"] == []

    history = client.get(
        "/api/v1/admin/config-history",
        params={"entity_id": str(rule_id), "action": "rule_retire"},
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert history.json()["pagination"]["total_items"] == 1
    audit = history.json()["items"][0]
    assert audit["previous_values"]["valid_to_version"] is None
    assert audit["previous_values"]["retired_at"] is None
    assert audit["new_values"]["valid_to_version"] == 3
    assert audit["new_values"]["retired_at"] is not None

    db.expire_all()
    ticket = db.get(Ticket, first_id)
    assert ticket is not None
    assert ticket.sla_hours_applied == Decimal(first_body["sla_hours_applied"])
    assert ticket.sla_deadline == datetime.fromisoformat(first_body["sla_deadline"])
    assert str(ticket.sla_config_version_id) == first_body["sla_config_version_id"]
    after = next(
        item
        for item in client.get(
            "/api/v1/me/work-queue", headers=auth(tech)
        ).json()["items"]
        if item["id"] == str(first_id)
    )["sla"]
    assert after == before

    second = client.post(
        "/api/v1/tickets",
        data={
            "title": "No funciona el correo",
            "description": "El cliente de correo muestra un error al enviar.",
            "priority_id": str(alta.id),
        },
        headers=auth(user),
    )
    assert second.status_code == 201
    assert second.json()["sla_hours_applied"] == "8.00"
    assert second.json()["sla_version"] == "v3"


def test_batch_is_atomic_when_a_change_is_invalid(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, inactive, alta, media, _ = _catalog(db)

    response = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                _upsert(red, alta, "2.00"),
                _upsert(inactive, media, "4.00"),
            ]
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "inactive_catalog_item"

    assert db.scalars(select(SlaRule)).all() == []
    versions = db.scalars(select(ConfigurationVersion)).all()
    assert [version.version for version in versions] == [1]


def test_rule_survives_priority_deactivation_and_can_be_retired(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, _, alta, _, _ = _catalog(db)

    created = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "3.00")]},
        headers=admin_headers,
    )
    assert created.status_code == 200
    rule_id = created.json()["items"][0]["id"]

    deactivated = client.post(
        f"/api/v1/admin/priorities/{alta.id}/updates",
        json={"expected_revision": 1, "is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200

    matrix = client.get("/api/v1/admin/sla-rules", headers=admin_headers)
    assert matrix.status_code == 200
    assert any(
        item["id"] == rule_id and item["hours"] == "3.00"
        for item in matrix.json()["items"]
    )
    active_priority_ids = {
        item["id"] for item in matrix.json()["combinations"]["priorities"]
    }
    assert str(alta.id) not in active_priority_ids

    retired = client.post(
        f"/api/v1/admin/sla-rules/{rule_id}/retirement",
        json={"expected_rule_id": rule_id},
        headers=admin_headers,
    )
    assert retired.status_code == 200
    assert retired.json()["items"] == []
    assert retired.json()["configuration_version"]["version"] == 4

    after = client.get("/api/v1/admin/sla-rules", headers=admin_headers)
    assert after.json()["items"] == []


def test_batch_rejects_duplicate_combinations_and_stale_ids(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, _, alta, _, _ = _catalog(db)

    duplicate = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                _upsert(red, alta, "2.00"),
                _upsert(red, alta, "3.00"),
            ]
        },
        headers=admin_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_sla_rule"

    existing = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "2.00")]},
        headers=admin_headers,
    )
    assert existing.status_code == 200

    stale = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "3.00", str(uuid.uuid4()))]},
        headers=admin_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_configuration"


def test_upsert_closes_previous_rule_and_records_metadata(
    client: TestClient, db: Session, admin_headers, admin_user
) -> None:
    red, _, alta, _, _ = _catalog(db)

    first = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "2.00")]},
        headers=admin_headers,
    )
    first_rule_id = first.json()["items"][0]["id"]

    second = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, "3.00", first_rule_id)]},
        headers=admin_headers,
    )
    assert second.status_code == 200
    second_rule_id = second.json()["items"][0]["id"]

    old = db.get(SlaRule, uuid.UUID(first_rule_id))
    new = db.get(SlaRule, uuid.UUID(second_rule_id))
    assert old is not None and new is not None
    assert old.valid_to_version == 3
    assert old.retired_at is None
    assert new.supersedes_id == old.id
    assert new.valid_from_version == 3

    audit = db.scalar(
        select(ConfigurationAuditEntry).where(
            ConfigurationAuditEntry.entity_id == new.id,
            ConfigurationAuditEntry.action == ConfigAction.rule_upsert,
        )
    )
    assert audit is not None
    assert audit.previous_values is not None
    assert audit.previous_values["hours"] == "2.00"
    assert audit.new_values is not None
    assert audit.new_values["hours"] == "3.00"

    retired = client.post(
        f"/api/v1/admin/sla-rules/{second_rule_id}/retirement",
        json={"expected_rule_id": second_rule_id},
        headers=admin_headers,
    )
    assert retired.status_code == 200
    db.refresh(new)
    assert new.valid_to_version == 4
    assert new.retired_at is not None
    assert new.retired_by_id == admin_user.id


@pytest.mark.parametrize("hours", ["0", "0.00", "-1.00", "abc", "1.234"])
def test_batch_rejects_invalid_rule_hours(
    client: TestClient, db: Session, admin_headers, hours: str
) -> None:
    red, _, alta, _, _ = _catalog(db)

    response = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert(red, alta, hours)]},
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"

    assert db.scalars(select(SlaRule)).all() == []
    versions = db.scalars(select(ConfigurationVersion)).all()
    assert [version.version for version in versions] == [1]


def test_batch_limit_and_empty_batch(client: TestClient, admin_headers) -> None:
    too_many = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": [_upsert_for_ids() for _ in range(21)]},
        headers=admin_headers,
    )
    assert too_many.status_code == 422

    empty = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={"changes": []},
        headers=admin_headers,
    )
    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "empty_batch"


def _upsert_for_ids():
    return {
        "operation": "upsert",
        "category_id": str(uuid.uuid4()),
        "priority_id": str(uuid.uuid4()),
        "hours": "2.00",
        "expected_rule_id": None,
    }
