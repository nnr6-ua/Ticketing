"""Contrato OpenAPI de HU-03: petición y respuesta de información."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "003-responder-peticion-tecnico"
    / "contracts"
    / "ticket-information.openapi.yaml"
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


def _url(ticket, suffix: str) -> str:
    return f"{API}/{ticket.id}/{suffix}"


def _workflow(client, ticket, headers) -> dict:
    response = client.get(_url(ticket, "workflow"), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _expected(client, ticket, headers) -> str:
    return _workflow(client, ticket, headers)["ticket"]["updated_at"]


def test_contract_declares_hu03_paths_schemas_and_enums() -> None:
    spec = _load_contract()
    assert spec["openapi"] == "3.1.0"
    paths = spec["paths"]
    assert "/tickets/{ticket_id}/information-requests" in paths
    assert "/tickets/{ticket_id}/information-responses" in paths
    for schema in (
        "InformationRequestRef",
        "InformationRequestRequest",
        "InformationRequestResponse",
        "InformationResponseRequest",
        "InformationResponseResponse",
    ):
        assert schema in spec["components"]["schemas"]
    event_types = spec["components"]["schemas"]["TimelineEventType"]["enum"]
    assert "information_request" in event_types
    assert "user_response" in event_types


def test_workflow_response_matches_hu03_contract(
    client, seeded_workflow, pending_information, auth_headers
) -> None:
    spec = _load_contract()
    headers = auth_headers(seeded_workflow.users["creador"])
    payload = _workflow(client, pending_information.ticket, headers)

    _validator(spec, "WorkflowResponse").validate(payload)
    assert payload["can_respond_to_information"] is True
    assert payload["awaiting_user_response"] is True
    assert payload["active_information_request"]["id"] == str(
        pending_information.request.id
    )
    assert payload["reminder_active"] is False
    assert payload["reminder_due_at"] is not None


def test_information_request_response_matches_contract(
    client, seeded_workflow, ticket_en_progreso, auth_headers
) -> None:
    spec = _load_contract()
    headers = auth_headers(seeded_workflow.users["tecnico_asignado"])
    response = client.post(
        _url(ticket_en_progreso, "information-requests"),
        headers=headers,
        json={
            "body": "  ¿Qué navegador usas?  ",
            "expected_updated_at": _expected(
                client, ticket_en_progreso, headers
            ),
            "request_id": str(uuid4()),
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    _validator(spec, "InformationRequestResponse").validate(payload)
    assert payload["changed"] is True
    assert payload["information_request"]["body"] == "¿Qué navegador usas?"
    assert payload["timeline_entries"][0]["type"] == "status_change"
    assert payload["timeline_entries"][1]["type"] == "information_request"


def test_information_response_response_matches_contract(
    client, seeded_workflow, pending_information, auth_headers
) -> None:
    spec = _load_contract()
    headers = auth_headers(seeded_workflow.users["creador"])
    response = client.post(
        _url(pending_information.ticket, "information-responses"),
        headers=headers,
        json={
            "body": "  Uso Chrome 131.  ",
            "expected_updated_at": _expected(
                client, pending_information.ticket, headers
            ),
            "request_id": str(uuid4()),
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    _validator(spec, "InformationResponseResponse").validate(payload)
    assert payload["changed"] is True
    assert payload["information_response"]["body"] == "Uso Chrome 131."
    assert payload["information_response"]["reply_to_id"] == str(
        pending_information.request.id
    )
    assert payload["timeline_entries"][0]["type"] == "status_change"
    assert payload["timeline_entries"][1]["type"] == "user_response"


def test_timeline_and_my_tickets_match_hu03_contract(
    client, seeded_workflow, pending_information, auth_headers
) -> None:
    spec = _load_contract()
    headers = auth_headers(seeded_workflow.users["creador"])

    timeline = client.get(
        _url(pending_information.ticket, "timeline"), headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    _validator(spec, "TimelineResponse").validate(timeline.json())

    mine = client.get("/api/v1/me/tickets", headers=headers)
    assert mine.status_code == 200, mine.text
    _validator(spec, "MyTicketsResponse").validate(mine.json())
