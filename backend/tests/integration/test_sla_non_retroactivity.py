from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    Priority,
    SlaOutcome,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
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


def _queue(client: TestClient, tech: User, *, status: str | None = None) -> list[dict]:
    params = {"status": status} if status else None
    response = client.get(
        "/api/v1/me/work-queue", params=params, headers=_headers(tech)
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _queue_item(
    client: TestClient,
    tech: User,
    ticket_id: uuid.UUID,
    *,
    status: str | None = None,
) -> dict:
    return next(
        item for item in _queue(client, tech, status=status) if item["id"] == str(ticket_id)
    )


def _assign(db: Session, ticket_id: uuid.UUID, tech_id: uuid.UUID) -> Ticket:
    db.expire_all()
    ticket = db.get(Ticket, ticket_id)
    assert ticket is not None
    ticket.assignee_id = tech_id
    db.commit()
    db.refresh(ticket)
    return ticket


def test_closed_ticket_keeps_sla_outcome_after_rule_change(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, alta, _, tech, creator = _setup(db)

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
    assert rule.status_code == 200, rule.text
    rule_id = rule.json()["items"][0]["id"]

    created = _create_ticket(client, creator, alta, "cerrado")
    assert created.status_code == 201, created.text
    frozen_deadline = datetime.fromisoformat(created.json()["sla_deadline"])
    ticket_id = uuid.UUID(created.json()["id"])
    ticket = _assign(db, ticket_id, tech.id)
    ticket.status = TicketStatus.cerrado
    ticket.finalized_at = ticket.sla_deadline + timedelta(minutes=30)
    ticket.closed_at = ticket.finalized_at
    db.commit()
    db.refresh(ticket)

    frozen = (
        ticket.sla_deadline,
        ticket.sla_hours_applied,
        ticket.sla_priority_level,
        ticket.sla_config_version_id,
        ticket.finalized_at,
    )
    before = _queue_item(client, tech, ticket_id, status="cerrado")
    assert before["sla"]["outcome"] == SlaOutcome.breached.value
    assert before["sla"]["deadline"] is not None
    assert before["sla"]["breach_delay_seconds"] == 1800

    changed_rule = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(red.id),
                    "priority_id": str(alta.id),
                    "hours": "12.00",
                    "expected_rule_id": rule_id,
                }
            ]
        },
        headers=admin_headers,
    )
    assert changed_rule.status_code == 200, changed_rule.text

    db.refresh(ticket)
    assert ticket.sla_deadline == frozen_deadline
    assert (
        ticket.sla_deadline,
        ticket.sla_hours_applied,
        ticket.sla_priority_level,
        ticket.sla_config_version_id,
        ticket.finalized_at,
    ) == frozen
    after = _queue_item(client, tech, ticket_id, status="cerrado")
    assert after["sla"] == before["sla"]
    assert after["sla"]["outcome"] == SlaOutcome.breached.value

    fresh = _create_ticket(client, creator, alta, "tras-cierre")
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["sla_hours_applied"] == "12.00"
    assert datetime.fromisoformat(fresh.json()["sla_deadline"]) != frozen_deadline
    assert fresh.json()["sla_version"] == "v3"


def test_base_hours_change_is_not_retroactive(
    client: TestClient, db: Session, admin_headers
) -> None:
    _, alta, _, tech, creator = _setup(db)

    open_created = _create_ticket(client, creator, alta, "abierto-base")
    assert open_created.status_code == 201, open_created.text
    open_id = uuid.UUID(open_created.json()["id"])
    open_ticket = _assign(db, open_id, tech.id)

    closed_created = _create_ticket(client, creator, alta, "cerrado-base")
    assert closed_created.status_code == 201, closed_created.text
    closed_id = uuid.UUID(closed_created.json()["id"])
    closed_ticket = _assign(db, closed_id, tech.id)
    closed_ticket.status = TicketStatus.cerrado
    closed_ticket.finalized_at = closed_ticket.sla_deadline + timedelta(hours=1)
    closed_ticket.closed_at = closed_ticket.finalized_at
    db.commit()
    db.refresh(closed_ticket)

    frozen_open = (
        open_ticket.sla_deadline,
        open_ticket.sla_hours_applied,
        open_ticket.sla_version,
        open_ticket.sla_config_version_id,
    )
    frozen_closed = (
        closed_ticket.sla_deadline,
        closed_ticket.sla_hours_applied,
        closed_ticket.sla_version,
        closed_ticket.sla_config_version_id,
    )
    before_open = _queue_item(client, tech, open_id, status="abierto")
    before_closed = _queue_item(client, tech, closed_id, status="cerrado")
    assert before_closed["sla"]["outcome"] == SlaOutcome.breached.value

    db.refresh(alta)
    changed_base = client.post(
        f"/api/v1/admin/priorities/{alta.id}/updates",
        json={"expected_revision": alta.revision, "base_hours": "4.00"},
        headers=admin_headers,
    )
    assert changed_base.status_code == 200, changed_base.text

    db.refresh(open_ticket)
    db.refresh(closed_ticket)
    assert (
        open_ticket.sla_deadline,
        open_ticket.sla_hours_applied,
        open_ticket.sla_version,
        open_ticket.sla_config_version_id,
    ) == frozen_open
    assert (
        closed_ticket.sla_deadline,
        closed_ticket.sla_hours_applied,
        closed_ticket.sla_version,
        closed_ticket.sla_config_version_id,
    ) == frozen_closed
    assert _queue_item(client, tech, open_id, status="abierto")["sla"] == before_open["sla"]
    assert _queue_item(client, tech, closed_id, status="cerrado")["sla"] == before_closed["sla"]

    fresh = _create_ticket(client, creator, alta, "tras-base")
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["sla_hours_applied"] == "4.00"
    assert fresh.json()["sla_version"] == "v2"
    assert datetime.fromisoformat(fresh.json()["sla_deadline"]) != frozen_open[0]


def test_queue_order_is_stable_when_priority_level_changes(
    client: TestClient, db: Session, admin_headers
) -> None:
    _, alta, baja, tech, creator = _setup(db)

    first = _create_ticket(client, creator, alta, "orden-uno")
    second = _create_ticket(client, creator, baja, "orden-dos")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_id = uuid.UUID(first.json()["id"])
    second_id = uuid.UUID(second.json()["id"])
    _assign(db, first_id, tech.id)
    _assign(db, second_id, tech.id)

    before = [item["id"] for item in _queue(client, tech)]
    assert before.index(str(first_id)) < before.index(str(second_id))

    db.refresh(baja)
    releveled = client.post(
        f"/api/v1/admin/priorities/{baja.id}/updates",
        json={"expected_revision": baja.revision, "level": 1},
        headers=admin_headers,
    )
    assert releveled.status_code == 200, releveled.text

    after = [item["id"] for item in _queue(client, tech)]
    assert after == before
    assert _queue_item(client, tech, first_id)["priority"]["level"] == 2
    assert _queue_item(client, tech, second_id)["priority"]["level"] == 4

    fresh = _create_ticket(client, creator, baja, "orden-nuevo")
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["sla_priority_level"] == 1


def test_deactivated_catalog_items_remain_visible_in_detail_and_history(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, alta, _, tech, creator = _setup(db)
    hardware = Category(name="Hardware", keywords=["portátil"], revision=1)
    db.add(hardware)
    db.commit()

    rule = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(red.id),
                    "priority_id": str(alta.id),
                    "hours": "3.00",
                    "expected_rule_id": None,
                }
            ]
        },
        headers=admin_headers,
    )
    assert rule.status_code == 200, rule.text

    created = _create_ticket(client, creator, alta, "inactivos")
    assert created.status_code == 201, created.text
    assert created.json()["category"]["name"] == "Red"
    ticket_id = uuid.UUID(created.json()["id"])
    ticket = _assign(db, ticket_id, tech.id)
    original_deadline = ticket.sla_deadline
    original_hours = ticket.sla_hours_applied
    before = _queue_item(client, tech, ticket_id)

    db.refresh(red)
    db.refresh(alta)
    deactivated_category = client.post(
        f"/api/v1/admin/categories/{red.id}/updates",
        json={"expected_revision": red.revision, "is_active": False},
        headers=admin_headers,
    )
    assert deactivated_category.status_code == 200, deactivated_category.text
    deactivated_priority = client.post(
        f"/api/v1/admin/priorities/{alta.id}/updates",
        json={"expected_revision": alta.revision, "is_active": False},
        headers=admin_headers,
    )
    assert deactivated_priority.status_code == 200, deactivated_priority.text

    after = _queue_item(client, tech, ticket_id)
    assert after["category"]["name"] == "Red"
    assert after["category"]["is_active"] is False
    assert after["priority"]["name"] == "Alta"
    assert after["priority"]["level"] == 2
    assert after["priority"]["is_active"] is False
    assert after["sla"]["deadline"] == before["sla"]["deadline"]
    assert after["sla"]["total_seconds"] == before["sla"]["total_seconds"]

    db.refresh(ticket)
    assert ticket.sla_deadline == original_deadline
    assert ticket.sla_hours_applied == original_hours

    timeline = client.get(
        f"/api/v1/tickets/{ticket_id}/timeline", headers=_headers(tech)
    )
    assert timeline.status_code == 200, timeline.text
    assert any(item["type"] == "created" for item in timeline.json()["items"])

    for entity_id, name in ((red.id, "Red"), (alta.id, "Alta")):
        history = client.get(
            "/api/v1/admin/config-history",
            params={"entity_id": str(entity_id), "action": "deactivate"},
            headers=admin_headers,
        )
        assert history.status_code == 200, history.text
        assert history.json()["pagination"]["total_items"] == 1
        entry = history.json()["items"][0]
        assert entry["entity_id"] == str(entity_id)
        assert entry["previous_values"]["name"] == name
        assert entry["new_values"]["is_active"] is False


def test_legacy_v1_ticket_does_not_freeze_priority_level(
    client: TestClient, db: Session, admin_headers
) -> None:
    red, alta, _, tech, creator = _setup(db)

    snapshot = _create_ticket(client, creator, alta, "snapshot")
    assert snapshot.status_code == 201, snapshot.text
    snapshot_body = snapshot.json()
    snapshot_id = uuid.UUID(snapshot_body["id"])
    _assign(db, snapshot_id, tech.id)

    legacy = Ticket(
        id=uuid.uuid4(),
        number="TK-009102",
        title="Ticket legado v1 sin snapshot",
        description="Ticket anterior a la línea base de configuración.",
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
    db.add(legacy)
    db.commit()

    db.refresh(alta)
    releveled = client.post(
        f"/api/v1/admin/priorities/{alta.id}/updates",
        json={"expected_revision": alta.revision, "level": 3},
        headers=admin_headers,
    )
    assert releveled.status_code == 200, releveled.text

    snapshot_item = _queue_item(client, tech, snapshot_id)
    legacy_item = _queue_item(client, tech, legacy.id)
    assert snapshot_body["sla_version"] == "v1"
    assert snapshot_body["sla_config_version_id"] is not None
    assert snapshot_item["priority"]["level"] == 2
    assert legacy.sla_config_version_id is None
    assert legacy_item["priority"]["level"] == 3


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
