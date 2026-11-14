"""Pruebas de contrato de `contracts/assignee-change.openapi.yaml` (HU-06).

Cubre T006, T043, T058, T074 y T082: validación de las respuestas reales contra
el OpenAPI, catálogo completo de errores, DTOs aditivos y `extra="forbid"`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.models import AssigneeChangeKind, EscalationLevel
from app.schemas.assignee_change import (
    AssigneeChangeOptions,
    EscalationRequest,
    ReassignmentRequest,
)
from app.schemas.notification import (
    MarkNotificationReadResponse,
    NotificationListResponse,
)
from app.schemas.ticket_workflow import TimelineEntry, WorkflowResponse
from tests.conftest import SeededAssigneeChange
from tests.integration._hu06 import (
    NOTIFICATIONS_API,
    count_notifications,
    entries,
    error_code,
    escalate,
    expected_updated_at,
    options,
    reassign,
    set_assignee,
    url,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "006-reasignar-escalar-ticket"
    / "contracts"
    / "assignee-change.openapi.yaml"
)
API = "/api/v1/tickets"


def _load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _validator(spec: dict, schema_name: str) -> Draft202012Validator:
    document = {
        "components": spec["components"],
        "$ref": f"#/components/schemas/{schema_name}",
    }
    return Draft202012Validator(document)


def _validate(payload: dict, schema_name: str) -> None:
    spec = _load_contract()
    errors = sorted(
        _validator(spec, schema_name).iter_errors(payload), key=lambda e: e.path
    )
    assert not errors, "\n".join(
        f"{list(error.path)}: {error.message}" for error in errors
    )


def _assert_error(response, *, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    payload = response.json()
    assert set(payload) == {"detail"}
    assert set(payload["detail"]) == {"code", "message"}
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert payload["detail"]["message"]
    _validate(payload, "ErrorResponse")
    return payload


def _active_ticket(seed: SeededAssigneeChange):
    return seed.tickets["activo"]


def _no_writes(db, ticket, before_entries: int, before_notifications: int) -> None:
    assert len(entries(db, ticket)) == before_entries
    assert count_notifications(db, ticket) == before_notifications


# ---------------------------------------------------------------------------
# Respuestas válidas
# ---------------------------------------------------------------------------
def test_options_response_matches_contract(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    response = options(client, ticket, auth_headers(seed.users["asignado"]))
    assert response.status_code == 200, response.text
    payload = response.json()

    _validate(payload, "AssigneeChangeOptions")
    assert payload["current_assignee"]["escalation_level_label"] == "Nivel 1"
    assert [candidate["name"] for candidate in payload["reassignment_candidates"]] == [
        "Técnico E"
    ]
    assert [target["value"] for target in payload["escalation_targets"]] == [
        "nivel_2",
        "especialista",
    ]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vary"] == "Authorization"


def test_reassignment_response_matches_contract(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()

    response = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Motivo contractual.",
        request_id=request_id,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _validate(payload, "AssigneeChangeResponse")
    assert payload["changed"] is True
    assert payload["timeline_entry"] is not None

    # Replay idempotente: `timeline_entry` nulo y `changed = false`.
    replay = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Motivo contractual.",
        expected=payload["ticket"]["updated_at"],
        request_id=request_id,
    )
    assert replay.status_code == 200, replay.text
    _validate(replay.json(), "AssigneeChangeResponse")
    assert replay.json()["changed"] is False
    assert replay.json()["timeline_entry"] is None
    assert response.headers["Cache-Control"] == "no-store"


def test_escalation_response_matches_contract(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])

    response = escalate(
        client, ticket, headers, "especialista", reason="Motivo contractual."
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _validate(payload, "AssigneeChangeResponse")
    assert payload["change_kind"] == "escalation"
    assert payload["from_escalation_level"] == "nivel_1"
    assert payload["to_escalation_level"] == "especialista"
    assert payload["timeline_entry"]["change_kind"] == "escalation"


def test_timeline_entries_match_contract(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])
    reassign(client, ticket, headers, seed.users["companero"], reason="Motivo.")

    response = client.get(url(ticket, "timeline"), headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"]
    for item in payload["items"]:
        _validate(item, "TimelineEntry")
    assignee_entry = payload["items"][-1]
    assert assignee_entry["type"] == "assignee_change"
    assert assignee_entry["change_kind"] == "reassignment"


def test_notification_responses_match_contract(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    destination = seed.users["companero"]
    reassign(
        client,
        ticket,
        auth_headers(seed.users["asignado"]),
        destination,
        reason="Motivo contractual.",
    )

    inbox = client.get(NOTIFICATIONS_API, headers=auth_headers(destination))
    assert inbox.status_code == 200, inbox.text
    payload = inbox.json()
    _validate(payload, "NotificationListResponse")
    assert payload["unread_count"] == 1

    notification_id = payload["items"][0]["id"]
    read = client.post(
        f"{NOTIFICATIONS_API}/{notification_id}/read",
        headers=auth_headers(destination),
    )
    assert read.status_code == 200, read.text
    _validate(read.json(), "MarkNotificationReadResponse")
    assert read.json()["changed"] is True


def test_workflow_response_is_additive_and_matches_contract(
    client, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    response = client.get(
        url(ticket, "workflow"), headers=auth_headers(seed.users["asignado"])
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _validate(payload, "WorkflowResponse")
    assert payload["can_reassign"] is True
    assert payload["can_escalate"] is True
    # Campos previos de HU-05 conservados.
    assert {
        "can_change_status",
        "can_comment_internally",
        "can_view_internal",
    } <= set(payload)


# ---------------------------------------------------------------------------
# Catálogo de errores
# ---------------------------------------------------------------------------
def test_options_error_catalog(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    before_entries = len(entries(db, ticket))
    before_notifications = count_notifications(db, ticket)

    _assert_error(
        client.get(url(ticket, "assignee-change-options")),
        status=401,
        code="not_authenticated",
    )
    _assert_error(
        options(client, ticket, auth_headers(seed.users["supervisor"])),
        status=403,
        code="forbidden",
    )
    _assert_error(
        options(client, ticket, auth_headers(seed.users["companero"])),
        status=403,
        code="not_ticket_assignee",
    )
    _assert_error(
        client.get(
            f"{API}/{uuid.uuid4()}/assignee-change-options",
            headers=auth_headers(seed.users["asignado"]),
        ),
        status=404,
        code="ticket_not_found",
    )
    _assert_error(
        options(
            client,
            seed.tickets["finalizado"],
            auth_headers(seed.users["asignado"]),
        ),
        status=409,
        code="ticket_finalized",
    )
    _no_writes(db, ticket, before_entries, before_notifications)


def test_reassignment_error_catalog(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    assigned = seed.users["asignado"]
    headers = auth_headers(assigned)
    expected = expected_updated_at(client, ticket, headers)
    before_entries = len(entries(db, ticket))
    before_notifications = count_notifications(db, ticket)

    def check(response, status, code):
        _assert_error(response, status=status, code=code)
        _no_writes(db, ticket, before_entries, before_notifications)

    check(
        client.post(
            url(ticket, "reassignments"),
            json={
                "new_assignee_id": str(seed.users["companero"].id),
                "reason": "Motivo.",
                "expected_updated_at": expected,
                "request_id": str(uuid.uuid4()),
            },
        ),
        401,
        "not_authenticated",
    )
    check(
        reassign(
            client, ticket, auth_headers(seed.users["supervisor"]),
            seed.users["companero"],
        ),
        403,
        "forbidden",
    )
    check(
        reassign(
            client, ticket, auth_headers(seed.users["companero"]),
            seed.users["companero"],
        ),
        403,
        "not_ticket_assignee",
    )
    check(
        client.post(
            f"{API}/{uuid.uuid4()}/reassignments",
            headers=headers,
            json={
                "new_assignee_id": str(seed.users["companero"].id),
                "reason": "Motivo.",
                "expected_updated_at": expected,
                "request_id": str(uuid.uuid4()),
            },
        ),
        404,
        "ticket_not_found",
    )
    check(
        reassign(
            client, seed.tickets["finalizado"], headers, seed.users["companero"]
        ),
        409,
        "ticket_finalized",
    )
    check(
        reassign(
            client,
            ticket,
            headers,
            seed.users["companero"],
            expected="2000-01-01T00:00:00+00:00",
        ),
        409,
        "stale_ticket",
    )
    check(reassign(client, ticket, headers, assigned), 422, "self_reassignment")
    check(
        reassign(client, ticket, headers, seed.users["creador_tecnico"]),
        422,
        "creator_not_assignable",
    )
    check(
        reassign(client, ticket, headers, seed.users["otro_equipo"]),
        422,
        "invalid_reassignment_target",
    )
    check(
        reassign(client, ticket, headers, seed.users["inactivo"]),
        422,
        "assignee_unavailable",
    )
    check(
        reassign(client, ticket, headers, seed.users["companero"], reason="   "),
        422,
        "reason_required",
    )
    check(
        reassign(
            client, ticket, headers, seed.users["companero"], reason="x" * 5001
        ),
        422,
        "reason_too_long",
    )
    check(
        reassign(
            client,
            ticket,
            headers,
            seed.users["companero"],
            body={
                "new_assignee_id": "no-es-un-uuid",
                "reason": "Motivo.",
                "expected_updated_at": expected,
                "request_id": str(uuid.uuid4()),
            },
        ),
        422,
        "invalid_request",
    )


def test_reassignment_request_id_reused_error(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()

    first = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Motivo.",
        request_id=request_id,
    )
    assert first.status_code == 200, first.text
    entries_after = len(entries(db, ticket))
    notifications_after = count_notifications(db, ticket)

    reused = reassign(
        client,
        ticket,
        headers,
        seed.users["companero"],
        reason="Otro motivo.",
        expected=first.json()["ticket"]["updated_at"],
        request_id=request_id,
    )
    _assert_error(reused, status=409, code="request_id_reused")
    _no_writes(db, ticket, entries_after, notifications_after)


def test_escalation_error_catalog(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])
    before_entries = len(entries(db, ticket))
    before_notifications = count_notifications(db, ticket)

    def check(response, status, code):
        _assert_error(response, status=status, code=code)
        _no_writes(db, ticket, before_entries, before_notifications)

    check(
        client.post(
            url(ticket, "escalations"),
            json={
                "target_level": "nivel_2",
                "reason": "Motivo.",
                "expected_updated_at": expected_updated_at(client, ticket, headers),
                "request_id": str(uuid.uuid4()),
            },
        ),
        401,
        "not_authenticated",
    )
    check(
        escalate(
            client, ticket, auth_headers(seed.users["supervisor"]), "nivel_2"
        ),
        403,
        "forbidden",
    )
    check(
        escalate(
            client, ticket, auth_headers(seed.users["companero"]), "nivel_2"
        ),
        403,
        "not_ticket_assignee",
    )
    check(
        client.post(
            f"{API}/{uuid.uuid4()}/escalations",
            headers=headers,
            json={
                "target_level": "nivel_2",
                "reason": "Motivo.",
                "expected_updated_at": expected_updated_at(client, ticket, headers),
                "request_id": str(uuid.uuid4()),
            },
        ),
        404,
        "ticket_not_found",
    )
    check(
        escalate(client, seed.tickets["finalizado"], headers, "nivel_2"),
        409,
        "ticket_finalized",
    )
    check(
        escalate(
            client,
            ticket,
            headers,
            "nivel_2",
            expected="2000-01-01T00:00:00+00:00",
        ),
        409,
        "stale_ticket",
    )
    check(
        escalate(
            client,
            ticket,
            headers,
            "",
            body={
                "target_level": "nivel_3",
                "reason": "Motivo.",
                "expected_updated_at": expected_updated_at(
                    client, ticket, headers
                ),
                "request_id": str(uuid.uuid4()),
            },
        ),
        422,
        "invalid_request",
    )

    # Nivel máximo y nivel no superior requieren cambiar el responsable actual.
    set_assignee(db, ticket, seed.users["especialista"])
    check(
        escalate(
            client, ticket, auth_headers(seed.users["especialista"]), "nivel_2"
        ),
        409,
        "no_higher_level",
    )

    set_assignee(db, ticket, seed.users["nivel_2"])
    check(
        escalate(client, ticket, auth_headers(seed.users["nivel_2"]), "nivel_1"),
        422,
        "invalid_escalation_level",
    )

    seed.users["nivel_2"].is_active = False
    db.commit()
    set_assignee(db, ticket, seed.users["asignado"])
    check(
        escalate(client, ticket, headers, "nivel_2"),
        409,
        "no_technicians_available",
    )


def test_escalation_request_id_reused_error(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])
    request_id = uuid.uuid4()

    first = escalate(
        client, ticket, headers, "nivel_2", reason="Motivo.", request_id=request_id
    )
    assert first.status_code == 200, first.text
    entries_after = len(entries(db, ticket))
    notifications_after = count_notifications(db, ticket)

    reused = escalate(
        client,
        ticket,
        headers,
        "especialista",
        reason="Motivo.",
        expected=first.json()["ticket"]["updated_at"],
        request_id=request_id,
    )
    _assert_error(reused, status=409, code="request_id_reused")
    _no_writes(db, ticket, entries_after, notifications_after)


def test_notifications_error_catalog(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers
) -> None:
    seed = seeded_assignee_change
    headers = auth_headers(seed.users["companero"])

    _assert_error(
        client.get(NOTIFICATIONS_API), status=401, code="not_authenticated"
    )
    _assert_error(
        client.get(f"{NOTIFICATIONS_API}?page_size=0", headers=headers),
        status=422,
        code="invalid_request",
    )
    _assert_error(
        client.get(f"{NOTIFICATIONS_API}?page_size=101", headers=headers),
        status=422,
        code="invalid_request",
    )
    _assert_error(
        client.post(
            f"{NOTIFICATIONS_API}/{uuid.uuid4()}/read", headers=headers
        ),
        status=404,
        code="notification_not_found",
    )


def test_internal_error_catalog(
    client, db, seeded_assignee_change: SeededAssigneeChange, auth_headers, monkeypatch
) -> None:
    seed = seeded_assignee_change
    ticket = _active_ticket(seed)
    headers = auth_headers(seed.users["asignado"])

    def boom(*args, **kwargs):
        raise RuntimeError("fallo inesperado")

    # GET opciones
    monkeypatch.setattr(
        "app.api.v1.tickets.get_assignee_change_options", boom
    )
    _assert_error(
        client.get(url(ticket, "assignee-change-options"), headers=headers),
        status=500,
        code="internal_error",
    )

    # POST reasignación
    monkeypatch.setattr("app.api.v1.tickets.reassign_ticket", boom)
    response = reassign(
        client, ticket, headers, seed.users["companero"], reason="Motivo."
    )
    _assert_error(response, status=500, code="internal_error")

    # POST escalado
    monkeypatch.setattr("app.api.v1.tickets.escalate_ticket", boom)
    response = escalate(client, ticket, headers, "nivel_2", reason="Motivo.")
    _assert_error(response, status=500, code="internal_error")

    # GET bandeja
    monkeypatch.setattr(
        "app.api.v1.notifications.list_notifications", boom
    )
    _assert_error(
        client.get(NOTIFICATIONS_API, headers=headers),
        status=500,
        code="internal_error",
    )

    # POST lectura
    monkeypatch.setattr(
        "app.api.v1.notifications.mark_notification_read", boom
    )
    _assert_error(
        client.post(f"{NOTIFICATIONS_API}/{uuid.uuid4()}/read", headers=headers),
        status=500,
        code="internal_error",
    )


# ---------------------------------------------------------------------------
# DTOs aditivos y `extra="forbid"`
# ---------------------------------------------------------------------------
def _valid_reassignment_payload() -> dict:
    return {
        "new_assignee_id": str(uuid.uuid4()),
        "reason": "Motivo.",
        "expected_updated_at": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
    }


def _valid_escalation_payload() -> dict:
    return {
        "target_level": "nivel_2",
        "reason": "Motivo.",
        "expected_updated_at": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
    }


def test_reassignment_request_dto_is_strict() -> None:
    parsed = ReassignmentRequest(**_valid_reassignment_payload())
    assert isinstance(parsed.request_id, uuid.UUID)
    assert isinstance(parsed.expected_updated_at, datetime)

    with pytest.raises(ValidationError):
        ReassignmentRequest(**{**_valid_reassignment_payload(), "extra": 1})

    for field in (
        "new_assignee_id",
        "reason",
        "expected_updated_at",
        "request_id",
    ):
        payload = _valid_reassignment_payload()
        payload.pop(field)
        with pytest.raises(ValidationError):
            ReassignmentRequest(**payload)

    # El motivo no se limita en el esquema para conservar los códigos de
    # negocio `reason_required`/`reason_too_long`.
    parsed = ReassignmentRequest(
        **{**_valid_reassignment_payload(), "reason": "x" * 5001}
    )
    assert len(parsed.reason) == 5001

    with pytest.raises(ValidationError):
        ReassignmentRequest(
            **{**_valid_reassignment_payload(), "request_id": "no-uuid"}
        )
    with pytest.raises(ValidationError):
        ReassignmentRequest(
            **{
                **_valid_reassignment_payload(),
                "expected_updated_at": "no-fecha",
            }
        )


def test_escalation_request_dto_is_strict() -> None:
    parsed = EscalationRequest(**_valid_escalation_payload())
    assert parsed.target_level == EscalationLevel.nivel_2

    with pytest.raises(ValidationError):
        EscalationRequest(**{**_valid_escalation_payload(), "assignee_id": str(uuid.uuid4())})
    with pytest.raises(ValidationError):
        EscalationRequest(
            **{**_valid_escalation_payload(), "target_level": "nivel_3"}
        )
    for field in ("target_level", "reason", "expected_updated_at", "request_id"):
        payload = _valid_escalation_payload()
        payload.pop(field)
        with pytest.raises(ValidationError):
            EscalationRequest(**payload)


def test_response_dtos_are_strict_and_additive() -> None:
    for model in (
        AssigneeChangeOptions,
        NotificationListResponse,
        MarkNotificationReadResponse,
        TimelineEntry,
        WorkflowResponse,
    ):
        assert model.model_config.get("extra") == "forbid"

    assert "can_reassign" in WorkflowResponse.model_fields
    assert "can_escalate" in WorkflowResponse.model_fields
    for field in (
        "change_kind",
        "previous_assignee",
        "new_assignee",
        "from_escalation_level",
        "from_escalation_level_label",
        "to_escalation_level",
        "to_escalation_level_label",
    ):
        assert field in TimelineEntry.model_fields

    assert set(AssigneeChangeKind) == {
        AssigneeChangeKind.reassignment,
        AssigneeChangeKind.escalation,
    }


def test_no_mutating_http_methods_are_defined() -> None:
    spec = _load_contract()
    for path, operations in spec["paths"].items():
        methods = set(operations)
        assert methods <= {"get", "post"}, path
        assert not methods & {"put", "patch", "delete"}, path
