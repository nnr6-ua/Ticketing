"""Pruebas de contrato contra `contracts/work-queue.openapi.yaml`."""

from __future__ import annotations

from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from tests.conftest import SeededQueue

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "004-prioritized-work-queue"
    / "contracts"
    / "work-queue.openapi.yaml"
)
ENDPOINT = "/api/v1/me/work-queue"


def _load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _validator(spec: dict, schema_name: str) -> Draft202012Validator:
    document = {
        "components": spec["components"],
        "$ref": f"#/components/schemas/{schema_name}",
    }
    return Draft202012Validator(document)


def test_contract_file_is_valid_yaml() -> None:
    spec = _load_contract()
    assert spec["openapi"] == "3.1.0"
    assert "/api/v1/me/work-queue" in spec["paths"]


def test_success_response_matches_contract(seeded_client) -> None:
    spec = _load_contract()
    response = seeded_client.client.get(
        ENDPOINT, headers=seeded_client.seed.header_for("a")
    )
    assert response.status_code == 200

    payload = response.json()
    _validator(spec, "WorkQueueResponse").validate(payload)
    assert payload["meta"]["timezone"] == "Europe/Madrid"
    assert payload["meta"]["server_time"].endswith("Z")
    assert payload["items"][0]["links"]["self"].startswith("/api/v1/tickets/")


def test_finalized_item_matches_contract(seeded_client) -> None:
    spec = _load_contract()
    payload = seeded_client.client.get(
        f"{ENDPOINT}?status=resuelto", headers=seeded_client.seed.header_for("a")
    ).json()

    _validator(spec, "WorkQueueResponse").validate(payload)
    item = payload["items"][0]
    assert item["sla"]["state"] == "finalized"
    assert item["sla"]["remaining_seconds"] is None
    assert item["sla"]["warning_threshold_seconds"] is None
    assert item["sla"]["outcome"] == "met"


def test_error_responses_match_contract(seeded_client, monkeypatch) -> None:
    spec = _load_contract()
    validator = _validator(spec, "ErrorResponse")
    seed: SeededQueue = seeded_client.seed
    client = seeded_client.client

    missing = client.get(ENDPOINT)
    assert missing.status_code == 401
    validator.validate(missing.json())

    forbidden = client.get(ENDPOINT, headers=seed.header_for("supervisor"))
    assert forbidden.status_code == 403
    validator.validate(forbidden.json())

    invalid = client.get(
        f"{ENDPOINT}?status=desconocido", headers=seed.header_for("a")
    )
    assert invalid.status_code == 422
    validator.validate(invalid.json())

    def boom(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr("app.api.v1.work_queue.build_work_queue", boom)
    server_error = client.get(ENDPOINT, headers=seed.header_for("a"))
    assert server_error.status_code == 500
    validator.validate(server_error.json())
