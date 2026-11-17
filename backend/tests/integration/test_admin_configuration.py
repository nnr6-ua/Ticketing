from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    ConfigurationVersion,
    Priority,
    SlaRule,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)


@pytest.fixture()
def admin(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        name="Administradora",
        email="admin.config@example.com",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def config_seed(db: Session, admin: User) -> SimpleNamespace:
    red = Category(name="Red", keywords=["vpn"], is_active=True, revision=1)
    otros = Category(
        name="Otros", is_default=True, is_active=True, revision=1
    )
    critica = Priority(
        name="Crítica",
        level=1,
        base_hours="4.00",
        is_default=True,
        is_active=True,
        revision=1,
    )
    baja = Priority(
        name="Baja",
        level=4,
        base_hours="72.00",
        is_active=True,
        revision=1,
    )
    db.add_all([red, otros, critica, baja])
    db.commit()
    return SimpleNamespace(
        admin=admin,
        red=red,
        otros=otros,
        critica=critica,
        baja=baja,
    )


def test_requires_admin(client: TestClient, db: Session, config_seed) -> None:
    tecnico = User(
        id=uuid.uuid4(),
        name="Técnico",
        email="tecnico.config@example.com",
        role=UserRole.tecnico,
        is_active=True,
    )
    db.add(tecnico)
    db.commit()

    from tests.conftest import make_token

    response = client.get(
        "/api/v1/admin/categories",
        headers={"Authorization": f"Bearer {make_token(tecnico)}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"


def test_category_crud_and_defaults(
    client: TestClient, db: Session, auth, config_seed
) -> None:
    headers = auth(config_seed.admin)

    response = client.post(
        "/api/v1/admin/categories",
        json={"name": "  Software  ", "keywords": ["app", "APP"]},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Software"
    assert body["keywords"] == ["app"]
    assert body["is_default"] is False
    assert body["revision"] == 1

    duplicate = client.post(
        "/api/v1/admin/categories",
        json={"name": "software"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_catalog_name"

    source = db.scalar(select(Category).where(Category.name == "Otros"))
    assert source is not None
    replacement = db.scalar(select(Category).where(Category.name == "Software"))
    assert replacement is not None

    missing_replacement = client.post(
        f"/api/v1/admin/categories/{source.id}/updates",
        json={"expected_revision": source.revision, "is_active": False},
        headers=headers,
    )
    assert missing_replacement.status_code == 422
    assert (
        missing_replacement.json()["detail"]["code"]
        == "default_replacement_required"
    )

    updated = client.post(
        f"/api/v1/admin/categories/{source.id}/updates",
        json={
            "expected_revision": source.revision,
            "is_active": False,
            "replacement_default_id": str(replacement.id),
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    db.refresh(replacement)
    assert replacement.is_default is True

    stale = client.post(
        f"/api/v1/admin/categories/{source.id}/updates",
        json={"expected_revision": source.revision, "name": "Otros 2"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_configuration"

    versions = db.scalars(select(ConfigurationVersion)).all()
    assert max(version.version for version in versions) >= 3


def test_priority_level_is_freed_when_inactive(
    client: TestClient, db: Session, auth, config_seed
) -> None:
    headers = auth(config_seed.admin)
    baja = config_seed.baja

    deactivated = client.post(
        f"/api/v1/admin/priorities/{baja.id}/updates",
        json={"expected_revision": baja.revision, "is_active": False},
        headers=headers,
    )
    assert deactivated.status_code == 200

    created = client.post(
        "/api/v1/admin/priorities",
        json={"name": "Planificada", "level": 4, "base_hours": "72.00"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["level"] == 4

    db.refresh(baja)
    reactivated = client.post(
        f"/api/v1/admin/priorities/{baja.id}/updates",
        json={"expected_revision": baja.revision, "is_active": True},
        headers=headers,
    )
    assert reactivated.status_code == 409
    assert reactivated.json()["detail"]["code"] == "duplicate_priority_level"


def test_matrix_versioning_snapshot_and_retirement(
    client: TestClient, db: Session, auth, config_seed
) -> None:
    headers = auth(config_seed.admin)
    matrix = client.get("/api/v1/admin/sla-rules", headers=headers)
    assert matrix.status_code == 200
    assert matrix.json()["items"] == []

    upsert = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(config_seed.red.id),
                    "priority_id": str(config_seed.critica.id),
                    "hours": "2.50",
                    "expected_rule_id": None,
                }
            ]
        },
        headers=headers,
    )
    assert upsert.status_code == 200
    body = upsert.json()
    assert body["configuration_version"]["version"] == 2
    assert body["items"][0]["hours"] == "2.50"
    rule_id = body["items"][0]["id"]

    # La versión v2 queda congelada en el ticket.
    creator = User(
        id=uuid.uuid4(),
        name="Solicitante",
        email="solicitante.sla@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    db.add(creator)
    db.commit()
    created = client.post(
        "/api/v1/tickets",
        data={
            "title": "No funciona la VPN",
            "description": "No puedo conectar desde ayer por la tarde.",
            "priority_id": str(config_seed.critica.id),
        },
        headers=auth(creator),
    )
    assert created.status_code == 201
    ticket_body = created.json()
    assert ticket_body["sla_version"] == "v2"
    assert ticket_body["sla_priority_level"] == 1
    assert ticket_body["sla_hours_applied"] == "2.50"

    updated = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(config_seed.red.id),
                    "priority_id": str(config_seed.critica.id),
                    "hours": "1.00",
                    "expected_rule_id": rule_id,
                }
            ]
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["configuration_version"]["version"] == 3

    ticket = db.scalar(select(Ticket).where(Ticket.number == ticket_body["ticket_number"]))
    assert ticket is not None
    assert ticket.sla_hours_applied == 2.5
    assert ticket.sla_version == "v2"
    assert ticket.sla_config_version_id is not None

    old_rule = db.get(SlaRule, uuid.UUID(rule_id))
    assert old_rule is not None
    assert old_rule.valid_to_version == 3

    retired = client.post(
        f"/api/v1/admin/sla-rules/{updated.json()['items'][0]['id']}/retirement",
        json={"expected_rule_id": updated.json()["items"][0]["id"]},
        headers=headers,
    )
    assert retired.status_code == 200
    assert retired.json()["items"] == []

    history = client.get(
        "/api/v1/admin/config-history",
        params={"entity_type": "sla_rule"},
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()["pagination"]["total_items"] >= 3
