"""Ciclo completo y trazabilidad pública de HU-03."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def test_response_without_assignee_makes_ticket_available_in_collective_queue(
    client, db, seeded_workflow, ticket_en_progreso, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    other_technician = auth_headers(seeded_workflow.users["tecnico_no_asignado"])
    creator = auth_headers(seeded_workflow.users["creador"])

    _post(
        client,
        ticket_en_progreso,
        "information-requests",
        technician,
        "¿Qué navegador usas?",
    )
    ticket_en_progreso.assignee_id = None
    db.commit()

    response = _post(
        client,
        ticket_en_progreso,
        "information-responses",
        creator,
        "Uso Chrome 131.",
    )
    assert response["ticket"]["status"] == "en_progreso"

    for headers in (technician, other_technician):
        queue = client.get("/api/v1/me/work-queue", headers=headers)
        assert queue.status_code == 200, queue.text
        assert ticket_en_progreso.number in [
            item["number"] for item in queue.json()["items"]
        ]


def test_successive_cycles_link_each_response_to_its_latest_request(
    client, db, seeded_workflow, ticket_en_progreso, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    creator = auth_headers(seeded_workflow.users["creador"])

    first_request = _post(
        client, ticket_en_progreso, "information-requests", technician, "¿Navegador?"
    )
    first_response = _post(
        client, ticket_en_progreso, "information-responses", creator, "Chrome 131."
    )
    second_request = _post(
        client, ticket_en_progreso, "information-requests", technician, "¿Sistema?"
    )
    second_response = _post(
        client, ticket_en_progreso, "information-responses", creator, "Windows 11."
    )

    assert (
        first_request["information_request"]["id"]
        != second_request["information_request"]["id"]
    )
    assert first_response["information_response"]["reply_to_id"] == first_request[
        "information_request"
    ]["id"]
    assert second_response["information_response"]["reply_to_id"] == second_request[
        "information_request"
    ]["id"]

    rows = _entries(db, ticket_en_progreso)
    assert [row.event_type for row in rows] == [
        TimelineEventType.status_change,
        TimelineEventType.information_request,
        TimelineEventType.status_change,
        TimelineEventType.user_response,
        TimelineEventType.status_change,
        TimelineEventType.information_request,
        TimelineEventType.status_change,
        TimelineEventType.user_response,
    ]
    request_ids = [
        row.id for row in rows if row.event_type == TimelineEventType.information_request
    ]
    linked_ids = [
        row.reply_to_id
        for row in rows
        if row.event_type == TimelineEventType.user_response
    ]
    assert linked_ids == request_ids


def test_quickstart_sections_5_to_8_end_to_end(
    client, db, seeded_workflow, ticket_en_progreso, auth_headers
):
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    creator = auth_headers(seeded_workflow.users["creador"])
    supervisor = auth_headers(seeded_workflow.users["supervisor"])
    unrelated = auth_headers(seeded_workflow.users["sin_relacion"])

    request = _post(
        client,
        ticket_en_progreso,
        "information-requests",
        technician,
        "¿Qué versión del navegador y sistema operativo usas?",
    )
    request_id = request["information_request"]["id"]

    workflow = _workflow(client, ticket_en_progreso, creator)
    assert workflow["can_respond_to_information"] is True
    assert workflow["awaiting_user_response"] is True
    assert workflow["active_information_request"]["body"] == (
        "¿Qué versión del navegador y sistema operativo usas?"
    )
    assert workflow["reminder_active"] is False

    def _mine():
        response = client.get("/api/v1/me/tickets", headers=creator)
        assert response.status_code == 200, response.text
        return next(
            item
            for item in response.json()["items"]
            if item["id"] == str(ticket_en_progreso.id)
        )

    summary = _mine()
    assert summary["awaiting_user_response"] is True
    assert summary["response_requested_at"] is not None
    assert summary["reminder_active"] is False

    status_change = db.scalars(
        select(TicketTimelineEntry)
        .where(
            TicketTimelineEntry.ticket_id == ticket_en_progreso.id,
            TicketTimelineEntry.event_type == "status_change",
            TicketTimelineEntry.to_status == "pendiente_usuario",
        )
        .order_by(TicketTimelineEntry.created_at.desc())
    ).first()
    assert status_change is not None
    status_change.created_at = datetime.now(timezone.utc) - timedelta(hours=49)
    db.commit()

    workflow = _workflow(client, ticket_en_progreso, creator)
    assert workflow["reminder_active"] is True
    assert workflow["reminder_due_at"] is not None
    assert _mine()["reminder_active"] is True

    entries_before = len(_entries(db, ticket_en_progreso))
    for _ in range(2):
        _workflow(client, ticket_en_progreso, creator)
        _mine()
    db.expire_all()
    refreshed = db.get(Ticket, ticket_en_progreso.id)
    assert refreshed is not None
    assert refreshed.status.value == "pendiente_usuario"
    assert len(_entries(db, ticket_en_progreso)) == entries_before

    expected = _expected(client, ticket_en_progreso, creator)
    response_url = _url(ticket_en_progreso, "information-responses")
    for body, code in (("   ", "information_response_required"), ("x" * 5001, "information_response_too_long")):
        bad = client.post(
            response_url,
            headers=creator,
            json={"body": body, "expected_updated_at": expected, "request_id": str(uuid4())},
        )
        assert bad.status_code == 422, bad.text
        assert bad.json()["detail"]["code"] == code

    forbidden = client.post(
        response_url,
        headers=unrelated,
        json={"body": "Respuesta ajena.", "expected_updated_at": expected, "request_id": str(uuid4())},
    )
    assert forbidden.status_code == 404, forbidden.text
    assert forbidden.json()["detail"]["code"] == "ticket_not_found"

    supervisor_response = client.post(
        response_url,
        headers=supervisor,
        json={"body": "Respuesta del supervisor.", "expected_updated_at": expected, "request_id": str(uuid4())},
    )
    assert supervisor_response.status_code == 403, supervisor_response.text
    assert supervisor_response.json()["detail"]["code"] == "forbidden"

    stale = client.post(
        response_url,
        headers=creator,
        json={
            "body": "Respuesta obsoleta.",
            "expected_updated_at": "2000-01-01T00:00:00Z",
            "request_id": str(uuid4()),
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "stale_ticket"

    response_id = str(uuid4())
    payload = {
        "body": "Uso Chrome 131 en Windows 11.",
        "expected_updated_at": expected,
        "request_id": response_id,
    }
    responded = client.post(response_url, headers=creator, json=payload)
    assert responded.status_code == 201, responded.text
    assert responded.json()["information_response"]["reply_to_id"] == request_id

    replay = client.post(response_url, headers=creator, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["changed"] is False

    reused = client.post(
        response_url,
        headers=creator,
        json={**payload, "body": "Otro texto con el mismo identificador."},
    )
    assert reused.status_code == 409, reused.text
    assert reused.json()["detail"]["code"] == "request_id_reused"

    workflow = _workflow(client, ticket_en_progreso, creator)
    assert workflow["ticket"]["status"] == "en_progreso"
    assert workflow["can_respond_to_information"] is False
    assert workflow["awaiting_user_response"] is False
    assert workflow["active_information_request"] is None
    assert workflow["reminder_active"] is False
    assert _mine()["reminder_active"] is False

    timeline = client.get(_url(ticket_en_progreso, "timeline"), headers=creator)
    assert timeline.status_code == 200, timeline.text
    items = timeline.json()["items"]
    assert [item["type"] for item in items] == [
        "status_change",
        "information_request",
        "status_change",
        "user_response",
    ]
    assert all(item["type"] != "internal_comment" for item in items)
    assert items[3]["reply_to_id"] == request_id

    technician_workflow = _workflow(client, ticket_en_progreso, technician)
    assert technician_workflow["can_request_information"] is True
    assert technician_workflow["active_information_request"] is None

    queue = client.get("/api/v1/me/work-queue", headers=technician)
    assert queue.status_code == 200, queue.text
    assert ticket_en_progreso.number in [
        item["number"] for item in queue.json()["items"]
    ]
