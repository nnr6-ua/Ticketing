"""Pruebas de integración de la bandeja de notificaciones (HU-06, US4, T054)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    AssigneeChangeKind,
    Notification,
    NotificationType,
    TicketStatus,
)
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    NOTIFICATIONS_API,
    add_timeline_entry,
    count_notifications,
    error_code,
    reassign,
    reload_ticket,
)


def inbox(client, headers, query: str = ""):
    return client.get(f"{NOTIFICATIONS_API}{query}", headers=headers)


def read(client, headers, notification_id):
    return client.post(
        f"{NOTIFICATIONS_API}/{notification_id}/read", headers=headers
    )


def _notification_for(
    db,
    seed: SeededAssigneeChange,
    *,
    recipient,
    previous,
    new,
    key: str,
    created_at,
    kind=AssigneeChangeKind.reassignment,
    is_read: bool = False,
    ticket=None,
) -> Notification:
    ticket = ticket or seed.tickets["activo"]
    entry = add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=previous,
        new=new,
        kind=kind,
        key=key,
        created_at=created_at,
    )
    row = Notification(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-notification-{key}"),
        recipient_id=recipient.id,
        ticket_id=ticket.id,
        timeline_entry_id=entry.id,
        type=(
            NotificationType.ticket_reassigned
            if kind == AssigneeChangeKind.reassignment
            else NotificationType.ticket_escalated
        ),
        ticket_number=ticket.number,
        ticket_title=ticket.title,
        previous_assignee_name=previous.name,
        is_read=is_read,
        created_at=created_at,
        read_at=created_at + timedelta(minutes=1) if is_read else None,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# Creación y snapshots
# ---------------------------------------------------------------------------
def test_reassignment_creates_one_notification_per_timeline_entry(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]

    response = reassign(
        client, ticket, auth_headers(assigned), destination, reason="Motivo."
    )
    assert response.status_code == 200, response.text

    rows = db.scalars(select(Notification)).all()
    assert len(rows) == 1
    notification = rows[0]
    assert notification.timeline_entry_id is not None
    assert count_notifications(db, ticket) == 1

    # La unicidad por `timeline_entry_id` impide duplicar la notificación.
    duplicate = Notification(
        recipient_id=destination.id,
        ticket_id=ticket.id,
        timeline_entry_id=notification.timeline_entry_id,
        type=NotificationType.ticket_reassigned,
        ticket_number=ticket.number,
        ticket_title=ticket.title,
        previous_assignee_name=assigned.name,
        is_read=False,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_notification_snapshots_and_no_reason_in_payload(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]
    reason = "Motivo privado que nunca debe salir en la bandeja."

    response = reassign(
        client, ticket, auth_headers(assigned), destination, reason=reason
    )
    assert response.status_code == 200, response.text

    current_ticket = reload_ticket(db, ticket)
    payload = inbox(client, auth_headers(destination)).json()
    assert payload["items"]
    item = payload["items"][0]
    assert item["type"] == "ticket_reassigned"
    assert item["ticket_id"] == str(ticket.id)
    assert item["ticket_number"] == current_ticket.number
    assert item["ticket_title"] == current_ticket.title
    assert item["previous_assignee_name"] == assigned.name
    assert item["is_read"] is False
    assert item["read_at"] is None
    # El motivo no forma parte del contrato de notificación.
    serialized = json.dumps(payload, ensure_ascii=False)
    assert reason not in serialized
    assert set(item) == {
        "id",
        "type",
        "ticket_id",
        "ticket_number",
        "ticket_title",
        "previous_assignee_name",
        "is_read",
        "created_at",
        "read_at",
    }


def test_escalation_creates_escalated_notification(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    headers = auth_headers(assigned)
    from tests.integration._hu06 import escalate

    response = escalate(client, ticket, headers, "nivel_2", reason="Motivo.")
    assert response.status_code == 200, response.text
    new_assignee = response.json()["new_assignee"]

    rows = db.scalars(select(Notification)).all()
    assert len(rows) == 1
    assert rows[0].type == NotificationType.ticket_escalated
    assert str(rows[0].recipient_id) == new_assignee["id"]
    assert rows[0].previous_assignee_name == assigned.name


# ---------------------------------------------------------------------------
# Orden, contador, filtros y paginación
# ---------------------------------------------------------------------------
def test_notifications_order_global_unread_count_and_unread_only(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    recipient = seed.users["companero"]
    previous = seed.users["asignado"]
    headers = auth_headers(recipient)

    first = _notification_for(
        db,
        seed,
        recipient=recipient,
        previous=previous,
        new=recipient,
        key="order-1",
        created_at=seed.now - timedelta(minutes=3),
        is_read=True,
    )
    second = _notification_for(
        db,
        seed,
        recipient=recipient,
        previous=previous,
        new=recipient,
        key="order-2",
        created_at=seed.now - timedelta(minutes=2),
    )
    third = _notification_for(
        db,
        seed,
        recipient=recipient,
        previous=previous,
        new=seed.users["nivel_2"],
        key="order-3",
        created_at=seed.now - timedelta(minutes=1),
        kind=AssigneeChangeKind.escalation,
    )

    payload = inbox(client, headers).json()
    ids = [item["id"] for item in payload["items"]]
    assert ids == [str(third.id), str(second.id), str(first.id)]
    # `unread_count` es global: no depende de la página ni de `unread_only`.
    assert payload["unread_count"] == 2
    assert payload["pagination"]["total_items"] == 3

    read_response = read(client, headers, third.id)
    assert read_response.status_code == 200
    assert read_response.json()["changed"] is True

    page_size_one = inbox(client, headers, "?page_size=1").json()
    assert len(page_size_one["items"]) == 1
    assert page_size_one["unread_count"] == 1
    assert page_size_one["pagination"]["total_pages"] == 3
    assert page_size_one["pagination"]["has_next"] is True

    unread = inbox(client, headers, "?unread_only=true").json()
    assert [item["id"] for item in unread["items"]] == [str(second.id)]
    assert unread["unread_count"] == 1


def test_page_size_valid_and_out_of_range(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    recipient = seed.users["companero"]
    previous = seed.users["asignado"]
    headers = auth_headers(recipient)

    for index in range(3):
        _notification_for(
            db,
            seed,
            recipient=recipient,
            previous=previous,
            new=recipient,
            key=f"page-{index}",
            created_at=seed.now - timedelta(minutes=3 - index),
        )

    for size in (1, 20, 100):
        response = inbox(client, headers, f"?page_size={size}")
        assert response.status_code == 200, response.text
        assert response.json()["pagination"]["page_size"] == size
        assert len(response.json()["items"]) == min(size, 3)

    for size in (0, 101):
        response = inbox(client, headers, f"?page_size={size}")
        assert response.status_code == 422, response.text
        assert error_code(response) == "invalid_request"

    response = inbox(client, headers, "?page=0")
    assert response.status_code == 422
    assert error_code(response) == "invalid_request"


def test_default_page_size_is_twenty(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    recipient = seed.users["companero"]
    previous = seed.users["asignado"]
    headers = auth_headers(recipient)

    for index in range(21):
        _notification_for(
            db,
            seed,
            recipient=recipient,
            previous=previous,
            new=recipient,
            key=f"default-{index}",
            created_at=seed.now - timedelta(minutes=21 - index),
        )

    payload = inbox(client, headers).json()
    assert payload["pagination"]["page_size"] == 20
    assert len(payload["items"]) == 20
    assert payload["pagination"]["total_pages"] == 2


# ---------------------------------------------------------------------------
# Lectura idempotente y aislamiento
# ---------------------------------------------------------------------------
def test_mark_read_is_idempotent(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    recipient = seed.users["companero"]
    previous = seed.users["asignado"]
    headers = auth_headers(recipient)
    row = _notification_for(
        db,
        seed,
        recipient=recipient,
        previous=previous,
        new=recipient,
        key="read-idempotent",
        created_at=seed.now,
    )

    first = read(client, headers, row.id)
    assert first.status_code == 200
    assert first.json()["changed"] is True
    assert first.json()["notification"]["is_read"] is True
    read_at = first.json()["notification"]["read_at"]
    assert read_at is not None

    second = read(client, headers, row.id)
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["notification"]["read_at"] == read_at

    refreshed = db.get(Notification, row.id)
    db.refresh(refreshed)
    assert refreshed.is_read is True
    assert refreshed.read_at is not None


def test_foreign_and_missing_notifications_return_not_found(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    owner = seed.users["companero"]
    outsider = seed.users["asignado"]
    previous = seed.users["asignado"]
    row = _notification_for(
        db,
        seed,
        recipient=owner,
        previous=previous,
        new=owner,
        key="foreign",
        created_at=seed.now,
    )

    response = read(client, auth_headers(outsider), row.id)
    assert response.status_code == 404
    assert error_code(response) == "notification_not_found"

    response = read(client, auth_headers(owner), uuid.uuid4())
    assert response.status_code == 404
    assert error_code(response) == "notification_not_found"

    # La notificación ajena no aparece en la bandeja del otro usuario.
    payload = inbox(client, auth_headers(outsider)).json()
    assert payload["items"] == []
    assert payload["unread_count"] == 0

    # Y sigue no leída para su propietario.
    refreshed = db.get(Notification, row.id)
    db.refresh(refreshed)
    assert refreshed.is_read is False


def test_inbox_isolated_per_recipient(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    first = seed.users["companero"]
    second = seed.users["asignado"]
    previous = seed.users["creador_tecnico"]

    _notification_for(
        db,
        seed,
        recipient=first,
        previous=previous,
        new=first,
        key="isolation-first",
        created_at=seed.now - timedelta(minutes=1),
    )
    _notification_for(
        db,
        seed,
        recipient=second,
        previous=previous,
        new=second,
        key="isolation-second",
        created_at=seed.now,
    )

    first_payload = inbox(client, auth_headers(first)).json()
    second_payload = inbox(client, auth_headers(second)).json()
    assert first_payload["pagination"]["total_items"] == 1
    assert second_payload["pagination"]["total_items"] == 1
    assert first_payload["items"][0]["id"] != second_payload["items"][0]["id"]


def test_requires_authentication(client) -> None:
    response = client.get(NOTIFICATIONS_API)
    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_cache_headers(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    headers = auth_headers(seeded_assignee_change.users["companero"])
    response = inbox(client, headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "Authorization" in response.headers["Vary"]


# ---------------------------------------------------------------------------
# Destinatario desconectado
# ---------------------------------------------------------------------------
def test_notification_persists_while_recipient_is_disconnected(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]

    # El destinatario no consulta su bandeja mientras se produce el cambio.
    response = reassign(
        client, ticket, auth_headers(assigned), destination, reason="Motivo."
    )
    assert response.status_code == 200, response.text

    # Al reconectar, la notificación sigue pendiente y no leída.
    payload = inbox(client, auth_headers(destination)).json()
    assert payload["unread_count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["is_read"] is False
    assert payload["items"][0]["ticket_number"] == ticket.number


def test_finalized_ticket_does_not_create_notification(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["finalizado"]
    headers = auth_headers(seed.users["asignado"])
    before = count_notifications(db, ticket)

    response = reassign(
        client, ticket, headers, seed.users["companero"], reason="Motivo."
    )
    assert response.status_code == 409
    assert error_code(response) == "ticket_finalized"
    assert count_notifications(db, ticket) == before
    assert ticket.status == TicketStatus.resuelto
