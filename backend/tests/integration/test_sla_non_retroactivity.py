from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Priority, Ticket, TicketStatus, User, UserRole
from tests.conftest import make_token


def _setup(db: Session):
    red = Category(name="Red", keywords=["vpn"], is_active=True, revision=1)
    alta = Priority(name="Alta", level=2, base_hours="8.00", is_active=True)
    baja = Priority(name="Baja", level=4, base_hours="72.00", is_active=True)
    tech = User(
        id=uuid.uuid4(),
        name="Técnica",
        email="tecnica.retro@example.com",
        role=UserRole.tecnico,
        is_active=True,
    )
    creator = User(
        id=uuid.uuid4(),
        name="Solicitante",
        email="solicitante.retro@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    db.add_all([red, alta, baja, tech, creator])
    db.commit()
    return red, alta, baja, tech, creator


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


def _create_ticket(client: TestClient, user: User, priority: Priority, suffix: str):
    return client.post(
        "/api/v1/tickets",
        data={
            "title": f"No funciona la VPN {suffix}",
            "description": "No puedo conectar desde ayer por la tarde.",
            "priority_id": str(priority.id),
        },
        headers=_headers(user),
    )


def test_ticket_snapshot_and_queue_level_do_not_change(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, alta, baja, tech, creator = _setup(db)

    rule = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(red.id),
                    "priority_id": str(alta.id),
                    "hours": "1.00",
                    "expected_rule_id": None,
                }
            ]
        },
        headers=admin_headers,
    )
    assert rule.status_code == 200
    rule_id = rule.json()["items"][0]["id"]

    created = _create_ticket(client, creator, alta, "uno")
    assert created.status_code == 201, created.text
    old_body = created.json()
    old_ticket = db.scalar(select(Ticket).where(Ticket.id == uuid.UUID(old_body["id"])))
    assert old_ticket is not None
    old_ticket.assignee_id = tech.id
    db.commit()
    old_deadline = old_ticket.sla_deadline
    old_hours = old_ticket.sla_hours_applied
    old_level = old_ticket.sla_priority_level
    old_version_id = old_ticket.sla_config_version_id
    assert old_level == 2
    assert old_hours == 1
    assert old_version_id is not None

    deactivated = client.post(
        f"/api/v1/admin/priorities/{baja.id}/updates",
        json={"expected_revision": baja.revision, "is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200

    db.refresh(alta)
    releveled = client.post(
        f"/api/v1/admin/priorities/{alta.id}/updates",
        json={"expected_revision": alta.revision, "level": 4},
        headers=admin_headers,
    )
    assert releveled.status_code == 200

    changed_rule = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(red.id),
                    "priority_id": str(alta.id),
                    "hours": "2.00",
                    "expected_rule_id": rule_id,
                }
            ]
        },
        headers=admin_headers,
    )
    assert changed_rule.status_code == 200

    db.refresh(old_ticket)
    assert old_ticket.sla_deadline == old_deadline
    assert old_ticket.sla_hours_applied == old_hours
    assert old_ticket.sla_priority_level == old_level
    assert old_ticket.sla_config_version_id == old_version_id

    queue = client.get("/api/v1/me/work-queue", headers=_headers(tech))
    assert queue.status_code == 200
    queued = next(
        item for item in queue.json()["items"] if item["id"] == str(input_ticket_id(old_body))
    )
    assert queued["priority"]["level"] == 2

    fresh = _create_ticket(client, creator, alta, "dos")
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["sla_priority_level"] == 4
    assert fresh.json()["sla_hours_applied"] == "2.00"


def test_legacy_ticket_uses_current_priority_level_in_queue(
    client: TestClient, db: Session
) -> None:
    red, alta, _, tech, creator = _setup(db)
    ticket = Ticket(
        id=uuid.uuid4(),
        number="TK-009100",
        title="Ticket legado sin snapshot",
        description="Ticket creado antes de la configuración versionada.",
        status=TicketStatus.abierto,
        creator_id=creator.id,
        assignee_id=tech.id,
        category_id=red.id,
        priority_id=alta.id,
        sla_priority_level=None,
        sla_hours_applied=None,
        sla_config_version_id=None,
        sla_version="v1",
    )
    db.add(ticket)
    db.commit()

    queue = client.get("/api/v1/me/work-queue", headers=_headers(tech))
    assert queue.status_code == 200
    item = next(row for row in queue.json()["items"] if row["number"] == "TK-009100")
    assert item["priority"]["level"] == 2


def input_ticket_id(body: dict) -> uuid.UUID:
    return uuid.UUID(body["id"])
