"""Ciclo completo y trazabilidad pública de HU-03."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket, TicketTimelineEntry, TimelineEventType

API = "/api/v1/tickets"


def _url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _workflow(client, ticket: Ticket, headers: dict[str, str]) -> dict:
    response = client.get(_url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _expected(client, ticket: Ticket, headers: dict[str, str]) -> str:
    return _workflow(client, ticket, headers)["ticket"]["updated_at"]


def _post(client, ticket: Ticket, suffix: str, headers, body: str):
    response = client.post(
        _url(ticket, suffix),
        headers=headers,
        json={
            "body": body,
            "expected_updated_at": _expected(client, ticket, headers),
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


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


def test_full_cycle_returns_ticket_to_queue_with_traceability(
    client, db, seeded_workflow, ticket_en_progreso, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    creator = auth_headers(seeded_workflow.users["creador"])

    request = _post(
        client,
        ticket_en_progreso,
        "information-requests",
        technician,
        "¿Qué navegador y sistema operativo usas?",
    )
    assert request["ticket"]["status"] == "pendiente_usuario"

    response = _post(
        client,
        ticket_en_progreso,
        "information-responses",
        creator,
        "Uso Chrome 131 en Windows 11.",
    )
    assert response["ticket"]["status"] == "en_progreso"
    assert response["information_response"]["reply_to_id"] == request[
        "information_request"
    ]["id"]

    rows = _entries(db, ticket_en_progreso)
    assert [row.event_type for row in rows] == [
        TimelineEventType.status_change,
        TimelineEventType.information_request,
        TimelineEventType.status_change,
        TimelineEventType.user_response,
    ]
    assert rows[0].from_status.value == "en_progreso"
    assert rows[0].to_status.value == "pendiente_usuario"
    assert rows[2].from_status.value == "pendiente_usuario"
    assert rows[2].to_status.value == "en_progreso"
    assert rows[1].author_id == seeded_workflow.users["tecnico_asignado"].id
    assert rows[3].author_id == seeded_workflow.users["creador"].id
    assert rows[3].reply_to_id == rows[1].id
    assert rows[1].is_internal is False
    assert rows[3].is_internal is False

    queue = client.get("/api/v1/me/work-queue", headers=technician)
    assert queue.status_code == 200, queue.text
    numbers = [item["number"] for item in queue.json()["items"]]
    assert ticket_en_progreso.number in numbers

    creator_timeline = client.get(_url(ticket_en_progreso, "timeline"), headers=creator)
    assert creator_timeline.status_code == 200
    types = [item["type"] for item in creator_timeline.json()["items"]]
    assert types == [
        "status_change",
        "information_request",
        "status_change",
        "user_response",
    ]

    technician_timeline = client.get(
        _url(ticket_en_progreso, "timeline"), headers=technician
    )
    assert technician_timeline.status_code == 200
    assert [item["type"] for item in technician_timeline.json()["items"]] == types


def test_creator_cannot_see_internal_comments_but_sees_information(
    client, seeded_workflow, ticket_en_progreso, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    creator = auth_headers(seeded_workflow.users["creador"])

    _post(
        client,
        ticket_en_progreso,
        "information-requests",
        technician,
        "¿Qué navegador usas?",
    )
    comment = client.post(
        _url(ticket_en_progreso, "internal-comments"),
        headers=technician,
        json={"body": "Nota privada.", "request_id": str(uuid4())},
    )
    assert comment.status_code == 201, comment.text

    timeline = client.get(_url(ticket_en_progreso, "timeline"), headers=creator)
    assert timeline.status_code == 200
    payload = timeline.json()["items"]
    assert any(item["type"] == "information_request" for item in payload)
    assert all(item["type"] != "internal_comment" for item in payload)
    assert "Nota privada." not in str(payload)


def test_information_entries_are_immutable_and_have_no_edit_endpoints(
    client, seeded_workflow, pending_information, auth_headers
):
    headers = auth_headers(seeded_workflow.users["creador"])
    entry_id = pending_information.request.id
    paths = [
        _url(pending_information.ticket, f"timeline/{entry_id}"),
        _url(pending_information.ticket, f"information-requests/{entry_id}"),
        _url(pending_information.ticket, f"information-responses/{entry_id}"),
    ]
    for path in paths:
        for method in ("patch", "put", "delete"):
            response = getattr(client, method)(path, headers=headers)
            assert response.status_code in (404, 405), (
                path,
                method,
                response.status_code,
            )


def test_response_is_rejected_when_ticket_is_finalized(
    client, seeded_workflow, auth_headers
):
    creator = auth_headers(seeded_workflow.users["creador"])
    for key in ("resuelto", "cerrado"):
        ticket = seeded_workflow.tickets[key]
        response = client.post(
            _url(ticket, "information-responses"),
            headers=creator,
            json={
                "body": "Respuesta tardía.",
                "expected_updated_at": _expected(client, ticket, creator),
                "request_id": str(uuid4()),
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "invalid_transition"
