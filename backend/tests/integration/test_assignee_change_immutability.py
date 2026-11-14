"""Inmutabilidad append-only del cambio de responsable (HU-06, T086/T093)."""

from __future__ import annotations

import uuid

import pytest

from app.main import app
from app.models import AssigneeChangeKind, TicketTimelineEntry
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    add_timeline_entry,
    count_notifications,
    entries,
    error_code,
    escalate,
    expected_updated_at,
    reassign,
    url,
)

HTTP_METHODS = {"PUT", "PATCH", "DELETE"}


def _naive(value):
    """Normaliza marcas de tiempo para comparar SQLite (sin tz) y Postgres (con tz)."""
    if value is None or value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def test_hu06_routes_only_expose_get_and_post(
    seeded_assignee_change: SeededAssigneeChange,
) -> None:
    ticket = seeded_assignee_change.tickets["activo"]
    paths = app.openapi()["paths"]
    relevant = {
        "/api/v1/tickets/{ticket_id}/assignee-change-options",
        "/api/v1/tickets/{ticket_id}/reassignments",
        "/api/v1/tickets/{ticket_id}/escalations",
        "/api/v1/me/notifications",
        "/api/v1/me/notifications/{notification_id}/read",
    }
    for path in relevant:
        assert path in paths, path
        methods = {method.upper() for method in paths[path]}
        assert methods <= {"GET", "POST"}, (path, methods)
        assert not (methods & HTTP_METHODS), (path, methods)


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
@pytest.mark.parametrize(
    "suffix", ["assignee-change-options", "reassignments", "escalations"]
)
def test_editing_assignee_change_through_http_is_not_allowed(
    client,
    seeded_assignee_change: SeededAssigneeChange,
    auth_headers,
    method,
    suffix,
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = getattr(client, method)(
        url(ticket, suffix),
        headers=headers,
        **({} if method == "delete" else {"json": {"reason": "Intento de edición."}}),
    )

    assert response.status_code == 405, response.text


def test_timeline_entries_have_no_write_endpoint(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    for method in ("put", "patch", "delete"):
        response = getattr(client, method)(
            url(ticket, "timeline"), headers=headers
        )
        assert response.status_code == 405, response.text


def test_rejections_do_not_write_rows(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]

    scenarios = [
        reassign(
            client,
            ticket,
            auth_headers(seed.users["asignado"]),
            seed.users["companero"],
            reason="   ",
        ),
        reassign(
            client,
            ticket,
            auth_headers(seed.users["creador_tecnico"]),
            seed.users["companero"],
        ),
        escalate(
            client,
            ticket,
            auth_headers(seed.users["supervisor"]),
            "nivel_2",
        ),
        escalate(
            client,
            ticket,
            auth_headers(seed.users["asignado"]),
            "nivel_2",
            expected="2000-01-01T00:00:00+00:00",
        ),
    ]

    for response in scenarios:
        assert response.status_code >= 400
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_replay_does_not_modify_previous_entries(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()
    expected = expected_updated_at(client, ticket, headers)

    first = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Motivo inmutable.",
        expected=expected,
        request_id=request_id,
    )
    assert first.status_code == 200, first.text
    stored = entries(db, ticket)
    assert len(stored) == 1
    snapshot = (
        stored[0].id,
        stored[0].body,
        stored[0].created_at,
        stored[0].previous_assignee_id,
        stored[0].new_assignee_id,
    )

    replay = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Motivo inmutable.",
        expected=expected,
        request_id=request_id,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["changed"] is False

    stored_after = entries(db, ticket)
    assert len(stored_after) == 1
    assert (
        stored_after[0].id,
        stored_after[0].body,
        stored_after[0].created_at,
        stored_after[0].previous_assignee_id,
        stored_after[0].new_assignee_id,
    ) == snapshot
    assert count_notifications(db, ticket) == 1


def test_success_does_not_rewrite_prior_history(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    history = add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=seed.users["creador_tecnico"],
        new=seed.users["asignado"],
        kind=AssigneeChangeKind.reassignment,
        key="immutability-prior",
        body="Entrada previa inmutable.",
    )
    snapshot = (
        history.id,
        history.body,
        _naive(history.created_at),
        history.previous_assignee_id,
        history.new_assignee_id,
        history.change_kind,
    )

    response = reassign(
        client,
        ticket,
        auth_headers(seed.users["asignado"]),
        seed.users["companero"],
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    stored = db.get(TicketTimelineEntry, snapshot[0])
    db.refresh(stored)
    assert (
        stored.id,
        stored.body,
        _naive(stored.created_at),
        stored.previous_assignee_id,
        stored.new_assignee_id,
        stored.change_kind,
    ) == snapshot
    assert len(entries(db, ticket)) == 2


def test_escalation_does_not_rewrite_prior_history(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    history = add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=seed.users["creador_tecnico"],
        new=seed.users["asignado"],
        kind=AssigneeChangeKind.reassignment,
        key="immutability-escalation-prior",
        body="Entrada previa inmutable.",
    )
    snapshot = (history.id, history.body, _naive(history.created_at))

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )
    assert response.status_code == 200, response.text

    db.expire_all()
    stored = db.get(TicketTimelineEntry, snapshot[0])
    db.refresh(stored)
    assert (stored.id, stored.body, _naive(stored.created_at)) == snapshot
    assert count_notifications(db, ticket) == 1


def test_error_codes_are_stable_for_immutability_gate(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    reused_request_id = uuid.uuid4()
    first = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Primero.",
        request_id=reused_request_id,
    )
    assert first.status_code == 200, first.text
    reused = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Segundo.",
        request_id=reused_request_id,
    )
    assert reused.status_code == 409
    assert error_code(reused) == "request_id_reused"
