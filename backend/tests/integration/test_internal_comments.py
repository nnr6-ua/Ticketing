"""Pruebas de integración de los comentarios internos (HU-05, US3)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)

API = "/api/v1/tickets"
STATUS_KEYS = [
    ("abierto", TicketStatus.abierto),
    ("en_progreso", TicketStatus.en_progreso),
    ("pendiente_usuario", TicketStatus.pendiente_usuario),
    ("resuelto", TicketStatus.resuelto),
    ("cerrado", TicketStatus.cerrado),
]


def _url(ticket: Ticket, suffix: str = "internal-comments") -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _post_comment(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    body: str,
    *,
    request_id: UUID | None = None,
):
    payload = {"body": body, "request_id": str(request_id or uuid4())}
    return client.post(_url(ticket), headers=headers, json=payload)


def _reload(db: Session, ticket: Ticket) -> Ticket:
    db.expire(ticket)
    db.refresh(ticket)
    return ticket


def _comment_entries(
    db: Session, ticket: Ticket, request_id: UUID | None = None
) -> list[TicketTimelineEntry]:
    db.expire_all()
    statement = (
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.internal_comment,
        )
        .order_by(TicketTimelineEntry.created_at.asc())
    )
    if request_id is not None:
        statement = statement.where(TicketTimelineEntry.request_id == request_id)
    return list(db.scalars(statement).unique().all())


def _all_entries(db: Session, ticket: Ticket) -> int:
    db.expire_all()
    return int(
        db.scalar(
            select(func.count())
            .select_from(TicketTimelineEntry)
            .where(TicketTimelineEntry.ticket_id == ticket.id)
        )
        or 0
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Alta en todos los estados
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key, expected_status", STATUS_KEYS)
def test_assigned_technician_can_comment_in_every_state(
    client, db, seeded_workflow, auth_headers, key, expected_status
) -> None:
    ticket = seeded_workflow.tickets[key]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _post_comment(
        client, ticket, headers, "  Revisado el entorno del usuario.  "
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["created"] is True
    entry = payload["entry"]
    assert entry["type"] == "internal_comment"
    assert entry["is_internal"] is True
    assert entry["body"] == "Revisado el entorno del usuario."
    assert entry["from_status"] is None
    assert entry["to_status"] is None
    assert entry["author"]["id"] == str(
        seeded_workflow.users["tecnico_asignado"].id
    )
    assert entry["author"]["role"] == "tecnico"

    _reload(db, ticket)
    assert ticket.status == expected_status
    rows = _comment_entries(db, ticket)
    assert len(rows) == 1
    assert rows[0].body == "Revisado el entorno del usuario."
    assert rows[0].is_internal is True
    assert rows[0].author_id == seeded_workflow.users["tecnico_asignado"].id


def test_comment_does_not_touch_ticket_status_or_timestamps(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    original_status = ticket.status
    original_updated_at = _as_utc(ticket.updated_at)
    original_finalized_at = _as_utc(ticket.finalized_at)
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _post_comment(client, ticket, headers, "Nota interna.")

    assert response.status_code == 201, response.text
    _reload(db, ticket)
    assert ticket.status == original_status
    assert _as_utc(ticket.updated_at) == original_updated_at
    assert _as_utc(ticket.finalized_at) == original_finalized_at


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("body", ["", " ", "\n\t  "])
def test_empty_or_whitespace_comment_is_rejected(
    client, db, seeded_workflow, auth_headers, body
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _post_comment(client, ticket, headers, body)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "comment_required"
    assert "vacío" in detail["message"]
    assert _all_entries(db, ticket) == 0


def test_comment_over_5000_characters_is_rejected(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _post_comment(client, ticket, headers, "a" * 5001)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "comment_too_long"
    assert "5.000" in detail["message"]
    assert _all_entries(db, ticket) == 0


def test_comment_at_the_5000_character_limit_is_accepted(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    body = "a" * 5000

    response = _post_comment(client, ticket, headers, body)

    assert response.status_code == 201, response.text
    assert response.json()["entry"]["body"] == body


@pytest.mark.parametrize(
    "payload",
    [
        {"body": "Nota interna."},
        {"body": "Nota interna.", "request_id": "no-es-un-uuid"},
        {"body": 123, "request_id": str(uuid4())},
        {"body": "Nota interna.", "request_id": str(uuid4()), "extra": True},
    ],
)
def test_malformed_comment_payload_returns_invalid_request(
    client, db, seeded_workflow, auth_headers, payload
) -> None:
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = client.post(_url(ticket), headers=headers, json=payload)

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_request"
    assert _all_entries(db, ticket) == 0


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------
def test_same_request_id_and_body_returns_existing_comment(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    first = _post_comment(
        client, ticket, headers, "  Nota idempotente.  ", request_id=request_id
    )
    second = _post_comment(
        client, ticket, headers, "Nota idempotente.", request_id=request_id
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["created"] is False
    assert second.json()["entry"]["id"] == first.json()["entry"]["id"]

    rows = _comment_entries(db, ticket, request_id)
    assert len(rows) == 1
    assert rows[0].body == "Nota idempotente."


def test_same_request_id_with_other_body_is_rejected(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    first = _post_comment(
        client, ticket, headers, "Primera nota.", request_id=request_id
    )
    assert first.status_code == 201, first.text

    response = _post_comment(
        client, ticket, headers, "Segunda nota distinta.", request_id=request_id
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "request_id_reused"
    rows = _comment_entries(db, ticket, request_id)
    assert len(rows) == 1
    assert rows[0].body == "Primera nota."


def test_same_request_id_after_reassignment_is_rejected(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    old_headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    new_headers = auth_headers(seeded_workflow.users["tecnico_no_asignado"])
    request_id = uuid4()

    first = _post_comment(
        client, ticket, old_headers, "Nota del técnico anterior.", request_id=request_id
    )
    assert first.status_code == 201, first.text

    ticket.assignee_id = seeded_workflow.users["tecnico_no_asignado"].id
    db.commit()

    response = _post_comment(
        client, ticket, new_headers, "Nota del técnico anterior.", request_id=request_id
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "request_id_reused"
    rows = _comment_entries(db, ticket, request_id)
    assert len(rows) == 1
    assert rows[0].author_id == seeded_workflow.users["tecnico_asignado"].id


# ---------------------------------------------------------------------------
# Autorización
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", ["supervisor", "admin", "creador"])
def test_non_technician_roles_are_forbidden(
    client, db, seeded_workflow, auth_headers, key
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users[key])

    response = _post_comment(client, ticket, headers, "No autorizado.")

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "forbidden"
    assert detail["message"] == "No tienes permiso para modificar este ticket."
    assert _all_entries(db, ticket) == 0


def test_unassigned_technician_is_rejected(
    client, db, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_no_asignado"])

    response = _post_comment(client, ticket, headers, "No autorizado.")

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "not_ticket_assignee"
    assert _all_entries(db, ticket) == 0


def test_anonymous_request_is_rejected(client, seeded_workflow) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]

    response = client.post(
        _url(ticket),
        json={"body": "Anónimo.", "request_id": str(uuid4())},
    )

    assert response.status_code == 401, response.text
    assert response.json()["detail"]["code"] == "not_authenticated"


def test_unknown_ticket_returns_not_found(
    client, seeded_workflow, auth_headers
) -> None:
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = client.post(
        f"{API}/{uuid4()}/internal-comments",
        headers=headers,
        json={"body": "Nota.", "request_id": str(uuid4())},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "ticket_not_found"
