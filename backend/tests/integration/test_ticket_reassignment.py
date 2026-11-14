"""Pruebas de integración de la reasignación de tickets (HU-06, US1, T029)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import (
    AssigneeChangeKind,
    EscalationLevel,
    NotificationType,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
)
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    add_timeline_entry,
    as_utc,
    count_notifications,
    entries,
    error_code,
    expected_updated_at,
    make_user,
    notification_rows,
    options,
    reassign,
    reload_ticket,
    url,
)


def test_reassignment_success_is_atomic_and_registers_history(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    destination = seed.users["companero"]
    headers = auth_headers(assigned)

    original = reload_ticket(db, ticket)
    original_updated_at = original.updated_at
    immutable = {
        "status": original.status,
        "priority_id": original.priority_id,
        "category_id": original.category_id,
        "sla_deadline": original.sla_deadline,
        "sla_version": original.sla_version,
        "finalized_at": original.finalized_at,
        "closed_at": original.closed_at,
        "creator_id": original.creator_id,
    }
    request_id = uuid.uuid4()

    response = reassign(
        client,
        ticket,
        headers,
        destination,
        reason="  Estoy de vacaciones; el compañero conoce el caso.  ",
        request_id=request_id,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] is True
    assert payload["message"] is None
    assert payload["ticket"]["assignee_id"] == str(destination.id)
    assert payload["ticket"]["status"] == "en_progreso"
    assert payload["change_kind"] == "reassignment"
    assert payload["previous_assignee"]["id"] == str(assigned.id)
    assert payload["new_assignee"]["id"] == str(destination.id)
    assert payload["from_escalation_level"] == "nivel_1"
    assert payload["to_escalation_level"] == "nivel_1"
    entry = payload["timeline_entry"]
    assert entry is not None
    assert entry["type"] == "assignee_change"
    assert entry["change_kind"] == "reassignment"
    assert entry["body"] == "Estoy de vacaciones; el compañero conoce el caso."
    assert entry["is_internal"] is False
    assert entry["from_status"] is None and entry["to_status"] is None
    assert entry["previous_assignee"]["id"] == str(assigned.id)
    assert entry["new_assignee"]["id"] == str(destination.id)
    assert entry["author"]["id"] == str(assigned.id)

    refreshed = reload_ticket(db, ticket)
    assert refreshed.assignee_id == destination.id
    for field, value in immutable.items():
        assert getattr(refreshed, field) == value, field
    assert refreshed.updated_at != original_updated_at

    stored = entries(db, ticket)
    assert len(stored) == 1
    stored_entry = stored[0]
    assert stored_entry.event_type == TimelineEventType.assignee_change
    assert stored_entry.request_id == request_id
    assert stored_entry.change_kind == AssigneeChangeKind.reassignment
    assert stored_entry.previous_assignee_id == assigned.id
    assert stored_entry.new_assignee_id == destination.id
    assert stored_entry.body == "Estoy de vacaciones; el compañero conoce el caso."

    notifications = notification_rows(db, ticket)
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.recipient_id == destination.id
    assert notification.type == NotificationType.ticket_reassigned
    assert notification.timeline_entry_id == stored_entry.id
    assert notification.ticket_number == ticket.number
    assert notification.ticket_title == ticket.title
    assert notification.previous_assignee_name == assigned.name

    # RF-033: la última entrada coincide con el responsable mostrado.
    latest = entries(db, ticket)[-1]
    assert latest.new_assignee_id == refreshed.assignee_id


def test_options_list_same_team_and_level_candidates(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = options(client, ticket, headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket_id"] == str(ticket.id)
    assert payload["status"] == "en_progreso"
    assert payload["current_assignee"]["id"] == str(seed.users["asignado"].id)
    assert payload["has_reassignment_candidates"] is True
    assert payload["has_available_escalation_target"] is True
    candidate_ids = [item["id"] for item in payload["reassignment_candidates"]]
    assert candidate_ids == [str(seed.users["companero"].id)]
    assert payload["reassignment_candidates"][0] == {
        "id": str(seed.users["companero"].id),
        "name": "Técnico E",
        "role": "tecnico",
        "team": "Soporte",
        "escalation_level": "nivel_1",
        "escalation_level_label": "Nivel 1",
    }
    assert [target["value"] for target in payload["escalation_targets"]] == [
        "nivel_2",
        "especialista",
    ]
    # El creador y el responsable actual nunca aparecen en las opciones.
    assert str(seed.users["creador_tecnico"].id) not in candidate_ids
    assert str(seed.users["asignado"].id) not in candidate_ids


def test_candidates_without_team_cover_the_whole_level(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    seed.users["asignado"].team = None
    db.commit()
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = options(client, ticket, headers)

    assert response.status_code == 200, response.text
    candidates = response.json()["reassignment_candidates"]
    assert [item["name"] for item in candidates] == ["Técnico D", "Técnico E"]
    assert {item["team"] for item in candidates} == {"Redes", "Soporte"}


def test_self_reassignment_is_rejected(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, seed.users["asignado"])

    assert response.status_code == 422
    assert error_code(response) == "self_reassignment"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_creator_cannot_be_reassignment_destination(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, seed.users["creador_tecnico"])

    assert response.status_code == 422
    assert error_code(response) == "creator_not_assignable"
    assert entries(db, ticket) == []


@pytest.mark.parametrize("reason", ["", "   ", "\n\t "])
def test_reason_required_after_trim(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, reason
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(
        client, ticket, headers, seed.users["companero"], reason=reason
    )

    assert response.status_code == 422
    assert error_code(response) == "reason_required"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_reason_too_long_is_rejected(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(
        client, ticket, headers, seed.users["companero"], reason="x" * 5001
    )

    assert response.status_code == 422
    assert error_code(response) == "reason_too_long"
    assert entries(db, ticket) == []


@pytest.mark.parametrize("reason", ["x", "x" * 5000])
def test_reason_boundaries_are_accepted(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, reason
) -> None:
    seed = seeded_assignee_change
    ticket = (
        seed.tickets["activo"]
        if len(reason) == 1
        else seed.tickets["creador_asignado"]
    )
    headers = auth_headers(seed.users["asignado"])

    response = reassign(
        client, ticket, headers, seed.users["companero"], reason=reason
    )

    assert response.status_code == 200, response.text
    assert response.json()["timeline_entry"]["body"] == reason


@pytest.mark.parametrize(
    "body",
    [
        {
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
        {
            "new_assignee_id": str(uuid.uuid4()),
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
        },
        {
            "new_assignee_id": "no-es-un-uuid",
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
        {
            "new_assignee_id": str(uuid.uuid4()),
            "reason": "Motivo.",
            "expected_updated_at": "no-es-una-fecha",
            "request_id": str(uuid.uuid4()),
        },
        {
            "new_assignee_id": str(uuid.uuid4()),
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": "no-es-un-uuid",
        },
        {
            "new_assignee_id": str(uuid.uuid4()),
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
            "campo_extra": True,
        },
    ],
)
def test_malformed_payload_returns_invalid_request(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, body
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, "", body=body)

    assert response.status_code == 422
    assert error_code(response) == "invalid_request"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_identical_replay_does_not_write(
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
    assert first.json()["changed"] is True
    entry_count = len(entries(db, ticket))
    notification_count = count_notifications(db, ticket)

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
    payload = second.json()
    assert payload["changed"] is False
    assert payload["timeline_entry"] is None
    assert payload["message"] == (
        "Esta reasignación ya se aplicó con el identificador de solicitud indicado."
    )
    assert payload["previous_assignee"]["id"] == str(seed.users["asignado"].id)
    assert payload["new_assignee"]["id"] == str(destination.id)
    assert len(entries(db, ticket)) == entry_count
    assert count_notifications(db, ticket) == notification_count


def test_replay_works_after_losing_assignment(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    """Un reintento de red sigue siendo idempotente aunque el actor ya no sea responsable."""

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    actor = seed.users["asignado"]
    destination = seed.users["companero"]
    request_id = uuid.uuid4()
    expected = expected_updated_at(client, ticket, auth_headers(actor))

    first = reassign(
        client,
        ticket,
        auth_headers(actor),
        destination,
        reason="Motivo de red.",
        expected=expected,
        request_id=request_id,
    )
    assert first.status_code == 200, first.text

    replay = reassign(
        client,
        ticket,
        auth_headers(actor),
        destination,
        reason="Motivo de red.",
        expected=expected,
        request_id=request_id,
    )

    assert replay.status_code == 200, replay.text
    assert replay.json()["changed"] is False
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 1


def test_reused_request_id_with_other_data_is_rejected(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()

    first = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Primer motivo.",
        request_id=request_id,
    )
    assert first.status_code == 200, first.text
    entry_count = len(entries(db, ticket))

    second = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Otro motivo distinto.",
        request_id=request_id,
    )

    assert second.status_code == 409
    assert error_code(second) == "request_id_reused"
    assert len(entries(db, ticket)) == entry_count
    assert count_notifications(db, ticket) == 1


def test_stale_expected_updated_at_returns_409_without_writing(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        expected="2000-01-01T00:00:00+00:00",
    )

    assert response.status_code == 409
    assert error_code(response) == "stale_ticket"
    assert reload_ticket(db, ticket).assignee_id == seed.users["asignado"].id
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


@pytest.mark.parametrize(
    ("target_key", "expected_code"),
    [
        ("nivel_2", "invalid_reassignment_target"),
        ("especialista", "invalid_reassignment_target"),
        ("otro_equipo", "invalid_reassignment_target"),
        ("inactivo", "assignee_unavailable"),
    ],
)
def test_invalid_reassignment_destinations(
    client,
    db,
    seeded_assignee_change: SeededAssigneeChange,
    auth_headers,
    target_key,
    expected_code,
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, seed.users[target_key])

    assert response.status_code == 422
    assert error_code(response) == expected_code
    assert entries(db, ticket) == []


def test_unknown_reassignment_destination_is_unavailable(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = reassign(client, ticket, headers, uuid.uuid4())

    assert response.status_code == 422
    assert error_code(response) == "assignee_unavailable"
    assert entries(db, ticket) == []


def test_notification_failure_rolls_back_everything(
    client,
    db,
    seeded_assignee_change: SeededAssigneeChange,
    auth_headers,
    monkeypatch,
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    headers = auth_headers(assigned)
    original = reload_ticket(db, ticket)
    original_updated_at = original.updated_at

    def _fail(*args, **kwargs):
        raise RuntimeError("fallo simulado al crear la notificación")

    monkeypatch.setattr(
        "app.services.assignee_change.create_assignee_change_notification",
        _fail,
    )

    response = reassign(client, ticket, headers, seed.users["companero"])

    assert response.status_code == 500
    assert error_code(response) == "internal_error"
    assert response.json()["detail"]["message"] == (
        "No se pudo guardar el cambio. El ticket no se ha modificado. "
        "Inténtalo de nuevo."
    )
    refreshed = reload_ticket(db, ticket)
    assert refreshed.assignee_id == assigned.id
    assert refreshed.updated_at == original_updated_at
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_consistency_between_ticket_and_last_entry_is_enforced(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    assigned = seed.users["asignado"]
    # El ticket apunta a `asignado`, pero la última entrada dice `companero`.
    add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=seed.users["creador_tecnico"],
        new=seed.users["companero"],
        kind=AssigneeChangeKind.reassignment,
        key="inconsistent",
    )
    headers = auth_headers(assigned)

    options_response = options(client, ticket, headers)
    assert options_response.status_code == 409
    assert error_code(options_response) == "assignee_inconsistent"

    command = reassign(client, ticket, headers, seed.users["companero"])
    assert command.status_code == 409
    assert error_code(command) == "assignee_inconsistent"
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 0


def test_previous_entry_is_not_rewritten(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    history = add_timeline_entry(
        db,
        ticket,
        seed=seed,
        previous=seed.users["creador_tecnico"],
        new=seed.users["asignado"],
        kind=AssigneeChangeKind.reassignment,
        key="prior",
        body="Entrada previa inmutable.",
    )
    snapshot = (
        history.id,
        history.body,
        as_utc(history.created_at),
        history.previous_assignee_id,
        history.new_assignee_id,
    )

    response = reassign(client, ticket, headers, seed.users["companero"])
    assert response.status_code == 200, response.text

    stored = db.get(TicketTimelineEntry, snapshot[0])
    db.refresh(stored)
    assert (
        stored.id,
        stored.body,
        as_utc(stored.created_at),
        stored.previous_assignee_id,
        stored.new_assignee_id,
    ) == snapshot


def test_reassignment_is_not_available_through_get(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = client.get(url(ticket, "reassignments"), headers=headers)

    assert response.status_code == 405
