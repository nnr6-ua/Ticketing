"""Pruebas de contrato de `contracts/ticket-workflow.openapi.yaml` (HU-05)."""

from __future__ import annotations

from pathlib import Path
from datetime import timedelta
from uuid import uuid4

import pytest
import yaml
from jsonschema import Draft202012Validator

from app.models import Ticket, TicketStatus, TicketTimelineEntry, TimelineEventType
from tests.conftest import SeededWorkflow

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "005-cambio-estado-resolucion"
    / "contracts"
    / "ticket-workflow.openapi.yaml"
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


def _url(ticket: Ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _workflow(client, ticket: Ticket, headers: dict[str, str]) -> dict:
    response = client.get(_url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _transition(
    client,
    ticket: Ticket,
    headers: dict[str, str],
    target: str,
    *,
    resolution=None,
    expected: str | None = None,
    request_id=None,
):
    body = {
        "target_status": target,
        "expected_updated_at": expected or _workflow(client, ticket, headers)["ticket"]["updated_at"],
        "request_id": str(request_id or uuid4()),
    }
    if resolution is not None:
        body["resolution"] = resolution
    return client.post(_url(ticket, "status-transitions"), headers=headers, json=body)


def _error(response, *, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    payload = response.json()
    assert set(payload) == {"detail"}
    assert set(payload["detail"]) == {"code", "message"}
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert payload["detail"]["message"]
    return payload


def _seed_entries(db, ticket: Ticket, seed: SeededWorkflow) -> None:
    author = seed.users["tecnico_asignado"]
    base = seed.now
    db.add(
        TicketTimelineEntry(
            ticket_id=ticket.id,
            event_type=TimelineEventType.status_change,
            from_status=TicketStatus.abierto,
            to_status=TicketStatus.en_progreso,
            body=None,
            is_internal=False,
            author_id=author.id,
            created_at=base,
            event_order=0,
            request_id=uuid4(),
        )
    )
    db.add(
        TicketTimelineEntry(
            ticket_id=ticket.id,
            event_type=TimelineEventType.resolution,
            from_status=None,
            to_status=TicketStatus.resuelto,
            body="Resolución del contrato.",
            is_internal=False,
            author_id=author.id,
            created_at=base,
            event_order=1,
            request_id=uuid4(),
        )
    )
    db.add(
        TicketTimelineEntry(
            ticket_id=ticket.id,
            event_type=TimelineEventType.internal_comment,
            from_status=None,
            to_status=None,
            body="Comentario interno del contrato.",
            is_internal=True,
            author_id=author.id,
            created_at=base + timedelta(minutes=1),
            event_order=0,
            request_id=uuid4(),
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Documento y estructuras de éxito
# ---------------------------------------------------------------------------
def test_user_response_transition_is_not_a_public_endpoint() -> None:
    spec = _load_contract()
    paths = spec["paths"]
    post_paths = {
        path for path, operations in paths.items() if "post" in operations
    }
    assert post_paths == {
        "/tickets/{ticket_id}/status-transitions",
        "/tickets/{ticket_id}/internal-comments",
    }
    assert not any("user-response" in path for path in paths)


def test_contract_file_declares_hu05_endpoints_and_schemas() -> None:
    spec = _load_contract()
    assert spec["openapi"] == "3.1.0"
    paths = spec["paths"]
    assert "/tickets/{ticket_id}/workflow" in paths
    assert "/tickets/{ticket_id}/status-transitions" in paths
    assert "/tickets/{ticket_id}/internal-comments" in paths
    assert "/tickets/{ticket_id}/timeline" in paths
    for schema in (
        "StatusOption",
        "AuthorRef",
        "TimelineEntry",
        "TicketWorkflowSnapshot",
        "WorkflowResponse",
        "StatusTransitionRequest",
        "StatusTransitionResponse",
        "InternalCommentRequest",
        "InternalCommentResponse",
        "Pagination",
        "TimelineResponse",
        "ErrorResponse",
    ):
        assert schema in spec["components"]["schemas"]


def test_workflow_response_matches_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    ticket = seeded_workflow.tickets["abierto"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    payload = _workflow(client, ticket, headers)

    _validator(spec, "WorkflowResponse").validate(payload)
    snapshot = payload["ticket"]
    assert set(snapshot) == {
        "id",
        "number",
        "title",
        "status",
        "status_label",
        "assignee_id",
        "creator_id",
        "finalized_at",
        "closed_at",
        "updated_at",
        "allowed_transitions",
    }
    assert snapshot["status"] == "abierto"
    assert snapshot["status_label"] == "Abierto"
    assert snapshot["allowed_transitions"] == [
        {"value": "en_progreso", "label": "En progreso"}
    ]
    assert payload["can_change_status"] is True
    assert payload["can_comment_internally"] is True
    assert payload["can_view_internal"] is True


def test_status_transition_response_matches_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = _transition(
        client, ticket, headers, "resuelto", resolution="  Solución del contrato.  "
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    _validator(spec, "StatusTransitionResponse").validate(payload)
    assert payload["changed"] is True
    assert payload["message"] is None
    assert payload["ticket"]["status"] == "resuelto"
    assert payload["ticket"]["finalized_at"] is not None
    assert payload["ticket"]["closed_at"] is None
    assert [entry["type"] for entry in payload["timeline_entries"]] == [
        "status_change",
        "resolution",
    ]
    resolution = payload["timeline_entries"][1]
    assert resolution["body"] == "Solución del contrato."
    assert resolution["to_status"] == "resuelto"
    assert resolution["is_internal"] is False


def test_noop_and_replay_responses_match_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "StatusTransitionResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    applied = _transition(
        client,
        ticket,
        headers,
        "pendiente_usuario",
        expected=_workflow(client, ticket, headers)["ticket"]["updated_at"],
        request_id=request_id,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["changed"] is True

    replay = _transition(
        client,
        ticket,
        headers,
        "pendiente_usuario",
        expected=_workflow(client, ticket, headers)["ticket"]["updated_at"],
        request_id=request_id,
    )
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    validator.validate(replay_payload)
    assert replay_payload["changed"] is False
    assert replay_payload["timeline_entries"] == []
    assert replay_payload["message"] == (
        "Esta transición ya se aplicó con el identificador de solicitud indicado."
    )

    noop = _transition(client, ticket, headers, "pendiente_usuario")
    assert noop.status_code == 200, noop.text
    noop_payload = noop.json()
    validator.validate(noop_payload)
    assert noop_payload["changed"] is False
    assert noop_payload["timeline_entries"] == []
    assert noop_payload["message"] == "El ticket ya se encuentra en ese estado."


def test_timeline_response_matches_contract(
    client, db, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    ticket = seeded_workflow.tickets["en_progreso"]
    _seed_entries(db, ticket, seeded_workflow)
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    response = client.get(
        _url(ticket, "timeline"), headers=headers, params={"page_size": 2}
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    _validator(spec, "TimelineResponse").validate(payload)
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 3,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }
    assert [item["type"] for item in payload["items"]] == [
        "status_change",
        "resolution",
    ]


def test_internal_comment_response_matches_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    ticket = seeded_workflow.tickets["cerrado"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    request_id = uuid4()

    created = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "  Nota del contrato.  ", "request_id": str(request_id)},
    )
    assert created.status_code == 201, created.text
    _validator(spec, "InternalCommentResponse").validate(created.json())
    assert created.json()["created"] is True
    assert created.json()["entry"]["body"] == "Nota del contrato."

    replayed = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "Nota del contrato.", "request_id": str(request_id)},
    )
    assert replayed.status_code == 200, replayed.text
    _validator(spec, "InternalCommentResponse").validate(replayed.json())
    assert replayed.json()["created"] is False
    assert replayed.json()["entry"]["id"] == created.json()["entry"]["id"]


# ---------------------------------------------------------------------------
# Contrato de errores
# ---------------------------------------------------------------------------
def test_authentication_and_authorisation_errors_match_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    payload = {
        "target_status": "resuelto",
        "resolution": "Solución.",
        "expected_updated_at": "2026-11-04T10:00:00Z",
        "request_id": str(uuid4()),
    }

    for response in (
        client.get(_url(ticket, "workflow")),
        client.post(_url(ticket, "status-transitions"), json=payload),
        client.get(_url(ticket, "timeline")),
        client.post(
            _url(ticket, "internal-comments"),
            json={"body": "Nota.", "request_id": str(uuid4())},
        ),
    ):
        validator.validate(_error(response, status=401, code="not_authenticated"))

    forbidden = client.post(
        _url(ticket, "status-transitions"),
        headers=auth_headers(seeded_workflow.users["supervisor"]),
        json=payload,
    )
    validator.validate(_error(forbidden, status=403, code="forbidden"))

    not_assignee = client.post(
        _url(ticket, "status-transitions"),
        headers=auth_headers(seeded_workflow.users["tecnico_no_asignado"]),
        json=payload,
    )
    validator.validate(_error(not_assignee, status=403, code="not_ticket_assignee"))


@pytest.mark.parametrize("key", ["supervisor", "admin", "creador"])
def test_missing_ticket_is_not_found_before_role_forbidden(
    client, auth_headers, key, seeded_workflow
) -> None:
    """Plan §1.2/§1.6: el 404 por ticket inexistente precede al 403 de rol."""

    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    headers = auth_headers(seeded_workflow.users[key])
    missing_id = uuid4()

    transition = client.post(
        f"{API}/{missing_id}/status-transitions",
        headers=headers,
        json={
            "target_status": "en_progreso",
            "expected_updated_at": "2026-11-04T10:00:00Z",
            "request_id": str(uuid4()),
        },
    )
    validator.validate(_error(transition, status=404, code="ticket_not_found"))

    comment = client.post(
        f"{API}/{missing_id}/internal-comments",
        headers=headers,
        json={"body": "Nota.", "request_id": str(uuid4())},
    )
    validator.validate(_error(comment, status=404, code="ticket_not_found"))


@pytest.mark.parametrize("key", ["supervisor", "admin", "creador"])
def test_write_forbidden_message_matches_catalog(
    client, seeded_workflow, auth_headers, key
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users[key])
    expected_message = "No tienes permiso para modificar este ticket."

    transition = client.post(
        _url(ticket, "status-transitions"),
        headers=headers,
        json={
            "target_status": "resuelto",
            "resolution": "Solución.",
            "expected_updated_at": "2026-11-04T10:00:00Z",
            "request_id": str(uuid4()),
        },
    )
    transition_payload = _error(transition, status=403, code="forbidden")
    assert transition_payload["detail"]["message"] == expected_message

    comment = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "Nota.", "request_id": str(uuid4())},
    )
    comment_payload = _error(comment, status=403, code="forbidden")
    assert comment_payload["detail"]["message"] == expected_message


def test_not_found_errors_match_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])
    unrelated = auth_headers(seeded_workflow.users["sin_relacion"])

    validator.validate(
        _error(
            client.get(_url(ticket, "workflow"), headers=unrelated),
            status=404,
            code="ticket_not_found",
        )
    )
    validator.validate(
        _error(
            client.get(_url(ticket, "timeline"), headers=unrelated),
            status=404,
            code="ticket_not_found",
        )
    )

    missing_id = uuid4()
    for response in (
        client.get(f"{API}/{missing_id}/workflow", headers=technician),
        client.get(f"{API}/{missing_id}/timeline", headers=technician),
        client.post(
            f"{API}/{missing_id}/status-transitions",
            headers=technician,
            json={
                "target_status": "en_progreso",
                "expected_updated_at": "2026-11-04T10:00:00Z",
                "request_id": str(uuid4()),
            },
        ),
        client.post(
            f"{API}/{missing_id}/internal-comments",
            headers=technician,
            json={"body": "Nota.", "request_id": str(uuid4())},
        ),
    ):
        validator.validate(_error(response, status=404, code="ticket_not_found"))


def test_conflict_error_codes_match_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    technician = auth_headers(seeded_workflow.users["tecnico_asignado"])

    abierto = seeded_workflow.tickets["abierto"]
    invalid = _transition(
        client, abierto, technician, "resuelto", resolution="Solución."
    )
    validator.validate(
        _error(invalid, status=409, code="invalid_transition")
    )

    cerrado = seeded_workflow.tickets["cerrado"]
    closed = _transition(client, cerrado, technician, "en_progreso")
    validator.validate(_error(closed, status=409, code="ticket_closed"))

    en_progreso = seeded_workflow.tickets["en_progreso"]
    stale = _transition(
        client,
        en_progreso,
        technician,
        "resuelto",
        resolution="Solución.",
        expected="2000-01-01T00:00:00Z",
    )
    validator.validate(_error(stale, status=409, code="stale_ticket"))

    request_id = uuid4()
    applied = _transition(
        client, abierto, technician, "en_progreso", request_id=request_id
    )
    assert applied.status_code == 200, applied.text
    reused = _transition(
        client, abierto, technician, "resuelto", request_id=request_id
    )
    validator.validate(_error(reused, status=409, code="request_id_reused"))


def test_validation_error_codes_match_contract(
    client, seeded_workflow, auth_headers
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    missing_resolution = _transition(client, ticket, headers, "resuelto")
    validator.validate(
        _error(missing_resolution, status=422, code="resolution_required")
    )

    too_long = _transition(
        client, ticket, headers, "resuelto", resolution="a" * 5001
    )
    validator.validate(
        _error(too_long, status=422, code="resolution_too_long")
    )

    not_allowed = _transition(
        client, ticket, headers, "pendiente_usuario", resolution="No aplica."
    )
    validator.validate(
        _error(not_allowed, status=422, code="resolution_not_allowed")
    )

    # RF-034: la resolución se rechaza aunque el destino coincida con el
    # estado actual, en lugar de aceptarse como no-op.
    same_status_not_allowed = _transition(
        client, ticket, headers, "en_progreso", resolution="No aplica."
    )
    validator.validate(
        _error(
            same_status_not_allowed, status=422, code="resolution_not_allowed"
        )
    )

    malformed = client.post(
        _url(ticket, "status-transitions"),
        headers=headers,
        json={
            "target_status": "resuelto",
            "expected_updated_at": "no-es-una-fecha",
            "request_id": "no-es-un-uuid",
        },
    )
    validator.validate(_error(malformed, status=422, code="invalid_request"))

    invalid_page = client.get(
        _url(ticket, "timeline"), headers=headers, params={"page": 0}
    )
    validator.validate(
        _error(invalid_page, status=422, code="invalid_request")
    )

    comment_required = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "   ", "request_id": str(uuid4())},
    )
    validator.validate(
        _error(comment_required, status=422, code="comment_required")
    )

    comment_too_long = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "a" * 5001, "request_id": str(uuid4())},
    )
    validator.validate(
        _error(comment_too_long, status=422, code="comment_too_long")
    )


def test_internal_error_matches_contract(
    client, seeded_workflow, auth_headers, monkeypatch
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    def _boom(*args, **kwargs):
        raise RuntimeError("fallo inesperado de prueba")

    monkeypatch.setattr("app.api.v1.tickets.change_status", _boom)

    response = _transition(
        client, ticket, headers, "resuelto", resolution="Solución."
    )

    payload = _error(response, status=500, code="internal_error")
    assert payload["detail"]["message"] == (
        "No se pudo guardar el cambio. El ticket no se ha modificado. "
        "Inténtalo de nuevo."
    )


def test_internal_comment_internal_error_matches_catalog(
    client, seeded_workflow, auth_headers, monkeypatch
) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])

    def _boom(*args, **kwargs):
        raise RuntimeError("fallo inesperado de prueba")

    monkeypatch.setattr("app.api.v1.tickets.add_internal_comment", _boom)

    response = client.post(
        _url(ticket, "internal-comments"),
        headers=headers,
        json={"body": "Nota interna.", "request_id": str(uuid4())},
    )

    payload = _error(response, status=500, code="internal_error")
    validator.validate(payload)
    assert payload["detail"]["message"] == (
        "No se pudo guardar el cambio. El ticket no se ha modificado. "
        "Inténtalo de nuevo."
    )
