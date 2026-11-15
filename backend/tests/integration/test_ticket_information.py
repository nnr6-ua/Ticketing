"""Pruebas de HU-03: peticiones y respuestas de información."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
)
from app.services.ticket_timeline import information_state

API = "/api/v1/tickets"
_UNSET = object()


def _url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _workflow(client, ticket: Ticket, headers: dict[str, str]) -> dict:
    response = client.get(_url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _expected(client, ticket: Ticket, headers: dict[str, str]) -> str:
    return _workflow(client, ticket, headers)["ticket"]["updated_at"]


def _request_information(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    *,
    body: str = "¿Qué versión del navegador usas?",
    expected: str | None = None,
    request_id: UUID | None = None,
):
    payload = {
        "body": body,
        "expected_updated_at": expected or _expected(client, ticket, headers),
        "request_id": str(request_id or uuid4()),
    }
    return client.post(
        _url(ticket, "information-requests"), headers=headers, json=payload
    )


def _respond_information(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    *,
    body: str = "Uso Chrome 131 en Windows 11.",
    expected: str | None = None,
    request_id: UUID | None = None,
):
    payload = {
        "body": body,
        "expected_updated_at": expected or _expected(client, ticket, headers),
        "request_id": str(request_id or uuid4()),
    }
    return client.post(
        _url(ticket, "information-responses"), headers=headers, json=payload
    )


def _entries(db: Session, ticket: Ticket) -> list[TicketTimelineEntry]:
    db.expire_all()
    statement = (
        select(TicketTimelineEntry)
        .where(TicketTimelineEntry.ticket_id == ticket.id)
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
    )
    return list(db.scalars(statement).unique().all())


def _error(response) -> str:
    return response.json()["detail"]["code"]


def test_request_information_changes_status_and_creates_public_entries(
    client, seeded_workflow, ticket_en_progreso, auth_headers, db
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _request_information(client, ticket_en_progreso, headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["changed"] is True
    assert body["message"] is None
    assert body["ticket"]["status"] == "pendiente_usuario"
    assert [entry["type"] for entry in body["timeline_entries"]] == [
        "status_change",
        "information_request",
    ]
    request = body["information_request"]
    assert request["body"] == "¿Qué versión del navegador usas?"
    assert request["requested_by"]["id"] == str(
        seeded_workflow.users["tecnico_asignado"].id
    )
    assert body["timeline_entries"][1]["reply_to_id"] is None

    detail = _workflow(client, ticket_en_progreso, headers)
    assert detail["can_request_information"] is False
    assert detail["awaiting_user_response"] is True
    assert detail["active_information_request"]["id"] == request["id"]

    creator_headers = auth_headers(seeded_workflow.users["creador"])
    detail = _workflow(client, ticket_en_progreso, creator_headers)
    assert detail["can_respond_to_information"] is True
    assert detail["reminder_active"] is False
    assert detail["reminder_due_at"] is not None


def test_request_information_requires_assigned_technician(
    client, seeded_workflow, ticket_en_progreso, auth_headers
):
    unassigned = auth_headers(seeded_workflow.users["tecnico_no_asignado"])
    response = _request_information(client, ticket_en_progreso, unassigned)
    assert response.status_code == 403
    assert _error(response) == "not_ticket_assignee"

    creator = auth_headers(seeded_workflow.users["creador"])
    response = _request_information(client, ticket_en_progreso, creator)
    assert response.status_code == 403
    assert _error(response) == "forbidden"

    admin = auth_headers(seeded_workflow.users["admin"])
    response = _request_information(client, ticket_en_progreso, admin)
    assert response.status_code == 403
    assert _error(response) == "forbidden"


def test_request_information_rejects_empty_and_too_long_body(
    client, seeded_workflow, ticket_en_progreso, auth_headers
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _request_information(client, ticket_en_progreso, headers, body="  ")
    assert response.status_code == 422
    assert _error(response) == "information_request_required"

    response = _request_information(
        client, ticket_en_progreso, headers, body="x" * 5001
    )
    assert response.status_code == 422
    assert _error(response) == "information_request_too_long"


def test_request_information_only_from_en_progreso(
    client, seeded_workflow, ticket_abierto, auth_headers
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    response = _request_information(client, ticket_abierto, headers)
    assert response.status_code == 409
    assert _error(response) == "invalid_transition"


def test_request_information_is_idempotent_and_detects_reuse(
    client, seeded_workflow, ticket_en_progreso, auth_headers
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    first = _request_information(
        client, ticket_en_progreso, headers, request_id=request_id
    )
    assert first.status_code == 201
    request_id_value = first.json()["information_request"]["id"]

    replay = _request_information(
        client,
        ticket_en_progreso,
        headers,
        expected=_workflow(client, ticket_en_progreso, headers)["ticket"]["updated_at"],
        request_id=request_id,
    )
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["changed"] is False
    assert body["timeline_entries"] == []
    assert body["information_request"]["id"] == request_id_value

    reused = client.post(
        _url(ticket_en_progreso, "information-requests"),
        headers=headers,
        json={
            "body": "Otra cosa distinta",
            "expected_updated_at": body["ticket"]["updated_at"],
            "request_id": str(request_id),
        },
    )
    assert reused.status_code == 409
    assert _error(reused) == "request_id_reused"


def test_request_information_rejects_already_open_request(
    client, seeded_workflow, pending_information, auth_headers
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    response = _request_information(client, pending_information.ticket, headers)
    assert response.status_code == 409
    assert _error(response) == "information_request_already_open"


def test_request_information_detects_stale_version(
    client, seeded_workflow, ticket_en_progreso, auth_headers, db
):
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    stale = "2020-01-01T00:00:00+00:00"
    response = _request_information(
        client, ticket_en_progreso, headers, expected=stale
    )
    assert response.status_code == 409
    assert _error(response) == "stale_ticket"


def test_response_returns_ticket_to_progress_and_links_request(
    client, seeded_workflow, pending_information, auth_headers, db
):
    headers = auth_headers(seeded_workflow.users["creador"])
    response = _respond_information(client, pending_information.ticket, headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["changed"] is True
    assert body["ticket"]["status"] == "en_progreso"
    assert [entry["type"] for entry in body["timeline_entries"]] == [
        "status_change",
        "user_response",
    ]
    entry = body["timeline_entries"][1]
    assert entry["reply_to_id"] == str(pending_information.request.id)
    assert entry["is_internal"] is False
    assert body["information_response"]["id"] == entry["id"]

    detail = _workflow(client, pending_information.ticket, headers)
    assert detail["awaiting_user_response"] is False
    assert detail["active_information_request"] is None
    assert detail["can_respond_to_information"] is False

    rows = _entries(db, pending_information.ticket)
    linked = [row for row in rows if row.event_type == TimelineEventType.user_response]
    assert len(linked) == 1
    assert linked[0].reply_to_id == pending_information.request.id


def test_response_is_idempotent_and_detects_reuse(
    client, seeded_workflow, pending_information, auth_headers
):
    headers = auth_headers(seeded_workflow.users["creador"])
    request_id = uuid4()
    first = _respond_information(
        client, pending_information.ticket, headers, request_id=request_id
    )
    assert first.status_code == 201
    response_id = first.json()["information_response"]["id"]

    expected = _workflow(client, pending_information.ticket, headers)["ticket"][
        "updated_at"
    ]
    replay = _respond_information(
        client,
        pending_information.ticket,
        headers,
        expected=expected,
        request_id=request_id,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["changed"] is False
    assert replay.json()["timeline_entries"] == []
    assert replay.json()["information_response"]["id"] == response_id

    reused = client.post(
        _url(pending_information.ticket, "information-responses"),
        headers=headers,
        json={
            "body": "Otra respuesta",
            "expected_updated_at": expected,
            "request_id": str(request_id),
        },
    )
    assert reused.status_code == 409
    assert _error(reused) == "request_id_reused"


def test_response_requires_creator(
    client, seeded_workflow, pending_information, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    response = _respond_information(client, pending_information.ticket, technician)
    assert response.status_code == 403
    assert _error(response) == "forbidden"

    expected = _workflow(
        client,
        pending_information.ticket,
        auth_headers(seeded_workflow.users["creador"]),
    )["ticket"]["updated_at"]
    other = auth_headers(seeded_workflow.users["sin_relacion"])
    response = _respond_information(
        client, pending_information.ticket, other, expected=expected
    )
    assert response.status_code == 404
    assert _error(response) == "ticket_not_found"


def test_response_rejects_invalid_state_and_stale_version(
    client, seeded_workflow, ticket_en_progreso, pending_information, auth_headers
):
    creator = auth_headers(seeded_workflow.users["creador"])
    response = _respond_information(client, ticket_en_progreso, creator)
    assert response.status_code == 409
    assert _error(response) == "invalid_transition"

    response = _respond_information(
        client,
        pending_information.ticket,
        creator,
        expected="2020-01-01T00:00:00+00:00",
    )
    assert response.status_code == 409
    assert _error(response) == "stale_ticket"


def test_response_rejects_empty_and_too_long_body(
    client, seeded_workflow, pending_information, auth_headers
):
    headers = auth_headers(seeded_workflow.users["creador"])
    response = _respond_information(client, pending_information.ticket, headers, body=" ")
    assert response.status_code == 422
    assert _error(response) == "information_response_required"

    response = _respond_information(
        client, pending_information.ticket, headers, body="x" * 5001
    )
    assert response.status_code == 422
    assert _error(response) == "information_response_too_long"


def test_reminder_is_derived_after_48_hours(
    client, db, seeded_workflow, pending_information, auth_headers
):
    old = seeded_workflow.now - timedelta(hours=49)
    pending_information.status_change.created_at = old
    pending_information.request.created_at = old
    pending_information.ticket.updated_at = old
    db.commit()

    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    detail = _workflow(client, pending_information.ticket, technician)
    assert detail["awaiting_user_response"] is True
    assert detail["reminder_active"] is True
    assert detail["reminder_due_at"] is not None

    creator = auth_headers(seeded_workflow.users["creador"])
    detail = _workflow(client, pending_information.ticket, creator)
    assert detail["reminder_active"] is True

    state = information_state(db, pending_information.ticket)
    assert state.active_request is not None
    assert state.reminder_active is True


def test_legacy_pending_ticket_without_request_shows_notice_not_reminder(
    client, seeded_workflow, ticket_pendiente_usuario, auth_headers
):
    headers = auth_headers(seeded_workflow.users["creador"])
    detail = _workflow(client, ticket_pendiente_usuario, headers)
    assert detail["awaiting_user_response"] is True
    assert detail["can_respond_to_information"] is True
    assert detail["active_information_request"] is None
    assert detail["reminder_active"] is False
    assert detail["reminder_due_at"] is None


def test_timeline_exposes_reply_to_id_only_to_authorized_viewers(
    client, seeded_workflow, pending_information, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    response = client.get(
        _url(pending_information.ticket, "timeline"), headers=technician
    )
    assert response.status_code == 200, response.text
    request_entries = [
        entry
        for entry in response.json()["items"]
        if entry["type"] == "information_request"
    ]
    assert len(request_entries) == 1
    assert request_entries[0]["reply_to_id"] is None


def test_my_tickets_projects_awaiting_and_reminder(
    client, db, seeded_workflow, pending_information, auth_headers
):
    old = seeded_workflow.now - timedelta(hours=49)
    pending_information.status_change.created_at = old
    pending_information.request.created_at = old
    db.commit()

    headers = auth_headers(seeded_workflow.users["creador"])
    response = client.get("/api/v1/me/tickets", headers=headers)
    assert response.status_code == 200, response.text
    ticket = next(
        item
        for item in response.json()["items"]
        if item["ticket_number"] == pending_information.ticket.number
    )
    assert ticket["awaiting_user_response"] is True
    assert ticket["reminder_active"] is True
    assert ticket["response_requested_at"] is not None
    assert ticket["reminder_due_at"] is not None
