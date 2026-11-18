"""Pruebas de contrato de `contracts/ticket-timeline.query.openapi.yaml` (HU-02)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.models import Ticket

API = "/api/v1/tickets"
CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "002-ticket-timeline-history"
    / "contracts"
    / "ticket-timeline.query.openapi.yaml"
)


def test_contract_documents_timeline_responses_and_event_types() -> None:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    responses = spec["paths"]["/tickets/{ticket_id}/timeline"]["get"]["responses"]
    assert set(responses) >= {"200", "401", "404", "422"}
    event_types = spec["components"]["schemas"]["TimelineEntry"]["properties"]["type"][
        "enum"
    ]
    assert "created" in event_types
    assert "internal_comment" in event_types


def _timeline(client, ticket: Ticket, headers: dict[str, str] | None = None, **params):
    return client.get(
        f"{API}/{ticket.id}/timeline", headers=headers, params=params
    )


def _assert_error(response, *, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    payload = response.json()
    assert set(payload) == {"detail"}
    assert set(payload["detail"]) == {"code", "message"}
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert payload["detail"]["message"]


def test_timeline_requires_authentication(client, seeded_workflow) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]

    response = _timeline(client, ticket)

    _assert_error(response, status=401, code="not_authenticated")


def test_timeline_hides_foreign_ticket_with_stable_error(
    client, seeded_workflow, auth_headers
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["sin_relacion"])

    response = _timeline(client, ticket, headers)

    _assert_error(response, status=404, code="ticket_not_found")
    assert "items" not in response.json()


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 201},
        {"page": "no-valido"},
    ],
)
def test_timeline_rejects_invalid_pagination(
    client, seeded_workflow, auth_headers, params
) -> None:
    ticket = seeded_workflow.tickets["en_progreso"]
    headers = auth_headers(seeded_workflow.users["creador"])

    response = _timeline(client, ticket, headers, **params)

    _assert_error(response, status=422, code="invalid_request")
