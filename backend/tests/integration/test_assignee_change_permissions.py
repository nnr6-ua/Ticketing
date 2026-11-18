"""Permisos, capacidades y estados del cambio de responsable (HU-06, T070)."""

from __future__ import annotations

import uuid

import pytest

from app.models import TicketStatus
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    add_timeline_entry,
    count_notifications,
    entries,
    error_code,
    escalate,
    expected_updated_at,
    options,
    reassign,
    reload_ticket,
    url,
)
from app.models import AssigneeChangeKind


def _all_routes(ticket) -> list[tuple[str, str]]:
    return [
        ("get", url(ticket, "assignee-change-options")),
        ("post", url(ticket, "reassignments")),
        ("post", url(ticket, "escalations")),
    ]


def _assert_capabilities(payload: dict, *, reassign: bool, escalate: bool) -> None:
    assert payload["can_reassign"] is reassign
    assert payload["can_escalate"] is escalate


# ---------------------------------------------------------------------------
# 401 / 404 / 403
# ---------------------------------------------------------------------------
def test_missing_token_returns_not_authenticated(
    client, seeded_assignee_change: SeededAssigneeChange
) -> None:
    ticket = seeded_assignee_change.tickets["activo"]
    body = {
        "new_assignee_id": str(seeded_assignee_change.users["companero"].id),
        "reason": "Motivo.",
        "expected_updated_at": "2026-11-10T09:15:30+00:00",
        "request_id": str(uuid.uuid4()),
    }

    for method, path in _all_routes(ticket):
        response = getattr(client, method)(path, json=body) if method == "post" else client.get(path)
        assert response.status_code == 401, response.text
        assert error_code(response) == "not_authenticated"


def test_missing_ticket_returns_not_found(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    headers = auth_headers(seed.users["asignado"])
    missing = uuid.uuid4()

    assert client.get(
        f"/api/v1/tickets/{missing}/assignee-change-options", headers=headers
    ).status_code == 404
    assert client.post(
        f"/api/v1/tickets/{missing}/reassignments",
        headers=headers,
        json={
            "new_assignee_id": str(seed.users["companero"].id),
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
    ).status_code == 404
    assert client.post(
        f"/api/v1/tickets/{missing}/escalations",
        headers=headers,
        json={
            "target_level": "nivel_2",
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
    ).status_code == 404


@pytest.mark.parametrize("key", ["supervisor", "admin", "usuario", "sin_relacion"])
def test_non_technician_roles_get_forbidden(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers, key
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users[key])

    options_response = options(client, ticket, headers)
    assert options_response.status_code == 403
    assert error_code(options_response) == "forbidden"

    reassign_response = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        expected="2000-01-01T00:00:00+00:00",
    )
    assert reassign_response.status_code == 403
    assert error_code(reassign_response) == "forbidden"

    escalate_response = escalate(
        client,
        ticket,
        headers,
        "nivel_2",
        expected="2000-01-01T00:00:00+00:00",
    )
    assert escalate_response.status_code == 403
    assert error_code(escalate_response) == "forbidden"


def test_inactive_user_token_is_rejected_before_authorization(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["inactivo"])

    response = options(client, ticket, headers)

    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_creator_technician_not_assigned_gets_forbidden_precedence(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    """RN-11: el creador técnico no asignado recibe `forbidden`, no `not_ticket_assignee`."""

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["creador_tecnico"])

    options_response = options(client, ticket, headers)
    assert options_response.status_code == 403
    assert error_code(options_response) == "forbidden"

    reassign_response = reassign(client, ticket, headers, seed.users["companero"])
    assert reassign_response.status_code == 403
    assert error_code(reassign_response) == "forbidden"

    escalate_response = escalate(client, ticket, headers, "nivel_2")
    assert escalate_response.status_code == 403
    assert error_code(escalate_response) == "forbidden"


@pytest.mark.parametrize("key", ["nivel_2", "otro_equipo"])
def test_unassigned_technician_gets_not_ticket_assignee(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers, key
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users[key])

    options_response = options(client, ticket, headers)
    assert options_response.status_code == 403
    assert error_code(options_response) == "not_ticket_assignee"

    reassign_response = reassign(client, ticket, headers, seed.users["companero"])
    assert reassign_response.status_code == 403
    assert error_code(reassign_response) == "not_ticket_assignee"

    escalate_response = escalate(client, ticket, headers, "nivel_2")
    assert escalate_response.status_code == 403
    assert error_code(escalate_response) == "not_ticket_assignee"


def test_creator_who_is_assigned_can_operate(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["creador_asignado"]
    creator = seed.users["asignado"]
    assert ticket.creator_id == creator.id
    headers = auth_headers(creator)

    response = reassign(client, ticket, headers, seed.users["companero"])

    assert response.status_code == 200, response.text
    assert reload_ticket(db, ticket).assignee_id == seed.users["companero"].id


# ---------------------------------------------------------------------------
# Capacidades antes y después del traspaso
# ---------------------------------------------------------------------------
def test_previous_technician_keeps_public_read_but_loses_write_capabilities(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    previous = seed.users["asignado"]
    new_assignee = seed.users["companero"]
    previous_headers = auth_headers(previous)
    new_headers = auth_headers(new_assignee)

    before_previous = client.get(url(ticket, "workflow"), headers=previous_headers)
    assert before_previous.status_code == 200, before_previous.text
    before_payload = before_previous.json()
    _assert_capabilities(before_payload, reassign=True, escalate=True)
    assert before_payload["can_change_status"] is True
    assert before_payload["can_comment_internally"] is True
    assert before_payload["can_view_internal"] is True

    before_new = client.get(url(ticket, "workflow"), headers=new_headers)
    assert before_new.status_code == 200, before_new.text
    _assert_capabilities(before_new.json(), reassign=False, escalate=False)
    assert before_new.json()["can_view_internal"] is False

    applied = reassign(client, ticket, previous_headers, new_assignee)
    assert applied.status_code == 200, applied.text

    after_previous = client.get(url(ticket, "workflow"), headers=previous_headers)
    assert after_previous.status_code == 200, after_previous.text
    after_previous_payload = after_previous.json()
    _assert_capabilities(after_previous_payload, reassign=False, escalate=False)
    assert after_previous_payload["can_change_status"] is False
    assert after_previous_payload["can_comment_internally"] is False
    assert after_previous_payload["can_view_internal"] is False

    after_new = client.get(url(ticket, "workflow"), headers=new_headers)
    assert after_new.status_code == 200, after_new.text
    after_new_payload = after_new.json()
    _assert_capabilities(after_new_payload, reassign=True, escalate=True)
    assert after_new_payload["can_change_status"] is True
    assert after_new_payload["can_comment_internally"] is True
    assert after_new_payload["can_view_internal"] is True

    # La lectura pública de la línea temporal se conserva para el anterior.
    assert client.get(url(ticket, "timeline"), headers=previous_headers).status_code == 200


# ---------------------------------------------------------------------------
# Estados admitidos y finalizados
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    [TicketStatus.abierto, TicketStatus.en_progreso, TicketStatus.pendiente_usuario],
)
def test_active_statuses_allow_the_change(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, status
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    ticket.status = status
    db.commit()
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, seed.users["companero"])

    assert response.status_code == 200, response.text
    assert reload_ticket(db, ticket).status == status


@pytest.mark.parametrize(
    ("key", "status"),
    [("finalizado", TicketStatus.resuelto)],
)
def test_finalized_ticket_rejects_options_and_commands(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, key, status
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets[key]
    headers = auth_headers(seed.users["asignado"])

    options_response = options(client, ticket, headers)
    assert options_response.status_code == 409
    assert error_code(options_response) == "ticket_finalized"

    reassign_response = reassign(client, ticket, headers, seed.users["companero"])
    assert reassign_response.status_code == 409
    assert error_code(reassign_response) == "ticket_finalized"

    escalate_response = escalate(client, ticket, headers, "nivel_2")
    assert escalate_response.status_code == 409
    assert error_code(escalate_response) == "ticket_finalized"

    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_closed_ticket_rejects_change(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    ticket.status = TicketStatus.cerrado
    ticket.finalized_at = seed.now
    ticket.closed_at = seed.now
    db.commit()
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, seed.users["companero"])

    assert response.status_code == 409
    assert error_code(response) == "ticket_finalized"
    assert entries(db, ticket) == []


def test_finalized_ticket_workflow_reports_no_capabilities(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["finalizado"]
    headers = auth_headers(seed.users["asignado"])

    response = client.get(url(ticket, "workflow"), headers=headers)

    assert response.status_code == 200, response.text
    _assert_capabilities(response.json(), reassign=False, escalate=False)


# ---------------------------------------------------------------------------
# Replay y consistencia
# ---------------------------------------------------------------------------
def test_identical_replay_returns_changed_false_without_writing(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    destination = seed.users["companero"]
    request_id = uuid.uuid4()
    expected = expected_updated_at(client, ticket, headers)

    first = reassign(
        client,
        ticket,
        headers,
        destination,
        reason="Motivo estable.",
        expected=expected,
        request_id=request_id,
    )
    assert first.status_code == 200, first.text

    second = reassign(
        client,
        ticket,
        headers,
        destination,
        reason="Motivo estable.",
        expected=expected,
        request_id=request_id,
    )

    assert second.status_code == 200, second.text
    assert second.json()["changed"] is False
    assert second.json()["timeline_entry"] is None
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 1


def test_inconsistent_assignee_blocks_options_and_commands(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=seed.users["creador_tecnico"],
        new=seed.users["companero"],
        kind=AssigneeChangeKind.reassignment,
        key="permissions-inconsistent",
    )
    headers = auth_headers(seed.users["asignado"])

    response = options(client, ticket, headers)
    assert response.status_code == 409
    assert error_code(response) == "assignee_inconsistent"

    command = reassign(client, ticket, headers, seed.users["companero"])
    assert command.status_code == 409
    assert error_code(command) == "assignee_inconsistent"
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 0
