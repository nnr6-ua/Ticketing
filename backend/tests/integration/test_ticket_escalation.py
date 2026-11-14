"""Pruebas de integración del escalado de tickets (HU-06, US2, T041)."""

from __future__ import annotations

import uuid

import pytest

from app.models import (
    AssigneeChangeKind,
    EscalationLevel,
    NotificationType,
    Ticket,
    TicketStatus,
    TimelineEventType,
)
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    count_notifications,
    entries,
    error_code,
    escalate,
    expected_updated_at,
    make_user,
    notification_rows,
    options,
    reload_ticket,
    set_assignee,
    url,
)


def _active_ticket(
    db, seed: SeededAssigneeChange, key: str, assignee
) -> Ticket:
    row = Ticket(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu06-escalation-ticket-{key}"),
        number=f"TK-9{key[-5:]}",
        title=f"Ticket de carga {key}",
        status=TicketStatus.en_progreso,
        priority_id=seed.priority.id,
        creator_id=seed.users["creador_tecnico"].id,
        assignee_id=assignee.id,
        created_at=seed.now,
        updated_at=seed.now,
        sla_version="v1",
    )
    db.add(row)
    db.commit()
    return row


def test_options_only_offer_strictly_higher_levels(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]

    def targets_for(user_key: str):
        set_assignee(db, ticket, seed.users[user_key])
        response = options(client, ticket, auth_headers(seed.users[user_key]))
        assert response.status_code == 200, response.text
        payload = response.json()
        return payload, [
            target["value"] for target in payload["escalation_targets"]
        ]

    payload, levels = targets_for("asignado")
    assert levels == ["nivel_2", "especialista"]
    assert payload["has_available_escalation_target"] is True

    payload, levels = targets_for("nivel_2")
    assert levels == ["especialista"]
    assert payload["has_available_escalation_target"] is True

    payload, levels = targets_for("especialista")
    assert levels == []
    assert payload["has_available_escalation_target"] is False


def test_escalation_to_nivel_2_selects_deterministic_technician(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    actor = seed.users["asignado"]
    destination = seed.users["nivel_2"]
    headers = auth_headers(actor)

    response = escalate(
        client, ticket, headers, "nivel_2", reason="Requiere Nivel 2."
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changed"] is True
    assert payload["change_kind"] == "escalation"
    assert payload["ticket"]["assignee_id"] == str(destination.id)
    assert payload["ticket"]["status"] == "en_progreso"
    assert payload["previous_assignee"]["id"] == str(actor.id)
    assert payload["new_assignee"]["id"] == str(destination.id)
    assert payload["from_escalation_level"] == "nivel_1"
    assert payload["to_escalation_level"] == "nivel_2"
    entry = payload["timeline_entry"]
    assert entry["type"] == "assignee_change"
    assert entry["change_kind"] == "escalation"
    assert entry["from_escalation_level"] == "nivel_1"
    assert entry["to_escalation_level"] == "nivel_2"
    assert entry["from_escalation_level_label"] == "Nivel 1"
    assert entry["to_escalation_level_label"] == "Nivel 2"

    refreshed = reload_ticket(db, ticket)
    assert refreshed.assignee_id == destination.id
    assert refreshed.status == TicketStatus.en_progreso
    stored = entries(db, ticket, TimelineEventType.assignee_change)
    assert len(stored) == 1
    assert stored[0].change_kind == AssigneeChangeKind.escalation
    assert stored[0].previous_assignee_id == actor.id
    assert stored[0].new_assignee_id == destination.id
    assert stored[0].new_assignee_id == refreshed.assignee_id

    notifications = notification_rows(db, ticket)
    assert len(notifications) == 1
    assert notifications[0].recipient_id == destination.id
    assert notifications[0].type == NotificationType.ticket_escalated
    assert notifications[0].previous_assignee_name == actor.name


def test_escalation_to_specialist(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    actor = seed.users["asignado"]
    headers = auth_headers(actor)

    response = escalate(client, ticket, headers, "especialista")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket"]["assignee_id"] == str(seed.users["especialista"].id)
    assert payload["from_escalation_level"] == "nivel_1"
    assert payload["to_escalation_level"] == "especialista"
    assert payload["timeline_entry"]["to_escalation_level_label"] == "Especialista"


def test_escalation_prefers_current_team(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()
    make_user(
        db, "external-l2", "A Técnico Externo", level="nivel_2", team="Redes"
    )
    local = make_user(
        db, "local-l2", "Z Técnico Local", level="nivel_2", team="Soporte"
    )
    db.commit()
    ticket = seed.tickets["activo"]

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )

    assert response.status_code == 200, response.text
    assert response.json()["ticket"]["assignee_id"] == str(local.id)


def test_escalation_uses_least_active_load_then_name(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    db.commit()
    busy = make_user(
        db, "busy-l2", "Técnico A", level="nivel_2", team="Soporte"
    )
    free = make_user(
        db, "free-l2", "Técnico Z", level="nivel_2", team="Soporte"
    )
    db.commit()
    for index in range(2):
        _active_ticket(db, seed, f"busy-{index}", busy)
    ticket = seed.tickets["activo"]

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )

    assert response.status_code == 200, response.text
    assert response.json()["ticket"]["assignee_id"] == str(free.id)


def test_escalation_falls_back_to_full_pool_without_team_candidate(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    seed.users["asignado"].team = "Redes"
    db.commit()
    external = make_user(
        db, "fallback-l2", "A Técnico Soporte", level="nivel_2", team="Soporte"
    )
    db.commit()
    ticket = seed.tickets["activo"]

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )

    assert response.status_code == 200, response.text
    assert response.json()["ticket"]["assignee_id"] in {
        str(external.id),
        str(seed.users["nivel_2"].id),
    }
    # Hay candidatos del pool completo: no se devuelve `no_technicians_available`.
    assert response.json()["changed"] is True


def test_escalation_excludes_creator_from_selection(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    creator = seed.users["creador_tecnico"]
    seed.users["nivel_2"].is_active = False
    creator.escalation_level = EscalationLevel.nivel_2
    db.commit()
    ticket = seed.tickets["activo"]

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )

    assert response.status_code == 409
    assert error_code(response) == "no_technicians_available"
    assert entries(db, ticket) == []


def test_no_higher_level_takes_precedence_over_invalid_level(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    set_assignee(db, ticket, seed.users["especialista"])
    headers = auth_headers(seed.users["especialista"])

    response = escalate(client, ticket, headers, "nivel_2")

    assert response.status_code == 409
    assert error_code(response) == "no_higher_level"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_no_technicians_available(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    seed.users["nivel_2"].is_active = False
    seed.users["especialista"].is_active = True
    db.commit()
    ticket = seed.tickets["activo"]

    response = escalate(
        client, ticket, auth_headers(seed.users["asignado"]), "nivel_2"
    )

    assert response.status_code == 409
    assert error_code(response) == "no_technicians_available"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


@pytest.mark.parametrize("target", ["nivel_1", "nivel_2"])
def test_non_higher_level_is_invalid(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, target
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    set_assignee(db, ticket, seed.users["nivel_2"])
    headers = auth_headers(seed.users["nivel_2"])

    response = escalate(client, ticket, headers, target)

    assert response.status_code == 422
    assert error_code(response) == "invalid_escalation_level"
    assert entries(db, ticket) == []


@pytest.mark.parametrize(
    "body",
    [
        {
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
        {
            "target_level": "nivel_3",
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
        },
        {
            "target_level": "nivel_2",
            "reason": "Motivo.",
            "expected_updated_at": "no-es-una-fecha",
            "request_id": str(uuid.uuid4()),
        },
        {
            "target_level": "nivel_2",
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": "no-es-un-uuid",
        },
        {
            "target_level": "nivel_2",
            "reason": "Motivo.",
            "expected_updated_at": "2026-11-10T09:15:30+00:00",
            "request_id": str(uuid.uuid4()),
            "assignee_id": str(uuid.uuid4()),
        },
    ],
)
def test_malformed_escalation_payload_is_invalid_request(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, body
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = escalate(client, ticket, headers, "", body=body)

    assert response.status_code == 422
    assert error_code(response) == "invalid_request"
    assert entries(db, ticket) == []
    assert count_notifications(db, ticket) == 0


def test_escalation_ignores_assignee_id_field(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    """El contrato no admite `assignee_id`: la persona la decide el servidor."""

    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    body = {
        "target_level": "nivel_2",
        "assignee_id": str(seed.users["especialista"].id),
        "reason": "No debe aceptarse.",
        "expected_updated_at": expected_updated_at(client, ticket, headers),
        "request_id": str(uuid.uuid4()),
    }

    response = escalate(client, ticket, headers, "", body=body)

    assert response.status_code == 422
    assert error_code(response) == "invalid_request"


def test_identical_escalation_replay_does_not_write(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()
    expected = expected_updated_at(client, ticket, headers)

    first = escalate(
        client,
        ticket,
        headers,
        "nivel_2",
        reason="Motivo estable.",
        expected=expected,
        request_id=request_id,
    )
    assert first.status_code == 200, first.text
    assert first.json()["changed"] is True

    second = escalate(
        client,
        ticket,
        headers,
        "nivel_2",
        reason="Motivo estable.",
        expected=expected,
        request_id=request_id,
    )

    assert second.status_code == 200, second.text
    payload = second.json()
    assert payload["changed"] is False
    assert payload["timeline_entry"] is None
    assert payload["message"] == (
        "Este escalado ya se aplicó con el identificador de solicitud indicado."
    )
    assert payload["from_escalation_level"] == "nivel_1"
    assert payload["to_escalation_level"] == "nivel_2"
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 1


def test_reused_escalation_request_id_with_other_level(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()

    first = escalate(
        client,
        ticket,
        headers,
        "nivel_2",
        reason="Mismo motivo.",
        request_id=request_id,
    )
    assert first.status_code == 200, first.text

    second = escalate(
        client,
        ticket,
        headers,
        "especialista",
        reason="Mismo motivo.",
        request_id=request_id,
    )

    assert second.status_code == 409
    assert error_code(second) == "request_id_reused"
    assert len(entries(db, ticket)) == 1
    assert count_notifications(db, ticket) == 1


def test_stale_escalation_does_not_write(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = escalate(
        client,
        ticket,
        headers,
        "nivel_2",
        expected="2000-01-01T00:00:00+00:00",
    )

    assert response.status_code == 409
    assert error_code(response) == "stale_ticket"
    assert entries(db, ticket) == []


def test_escalation_registers_to_level_greater_than_from(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = escalate(client, ticket, headers, "especialista")

    assert response.status_code == 200, response.text
    entry = entries(db, ticket)[-1]
    order = {
        EscalationLevel.nivel_1: 0,
        EscalationLevel.nivel_2: 1,
        EscalationLevel.especialista: 2,
    }
    assert order[entry.to_escalation_level] > order[entry.from_escalation_level]
    assert entry.to_escalation_level == EscalationLevel.especialista


def test_escalation_is_not_available_through_get(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = seed.tickets["activo"]
    headers = auth_headers(seed.users["asignado"])

    response = client.get(url(ticket, "escalations"), headers=headers)

    assert response.status_code == 405
