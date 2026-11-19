from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.core.errors import ADMIN_FORBIDDEN_MESSAGE, CONFIGURATION_ERROR_MESSAGES
from app.main import app
from app.models import ConfigAction, ConfigEntityType

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "008-configuracion-plazos-sla"
    / "contracts"
    / "admin-configuration.openapi.yaml"
)


def _contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_paths_and_methods_are_implemented() -> None:
    contract = _contract()
    application = app.openapi()

    for path, operations in contract["paths"].items():
        assert path in application["paths"], path
        for method in operations:
            if method.startswith("x-"):
                continue
            assert method in application["paths"][path], (path, method)


def _required_fields(schema: dict, schemas: dict | None = None) -> set[str]:
    fields = set(schema.get("required", []))
    for part in schema.get("allOf", []):
        if "$ref" in part and schemas is not None:
            name = part["$ref"].rsplit("/", 1)[-1]
            fields.update(_required_fields(schemas[name], schemas))
        else:
            fields.update(_required_fields(part, schemas))
    return fields


def test_contract_schemas_keep_required_fields() -> None:
    contract = _contract()["components"]["schemas"]
    application = app.openapi()["components"]["schemas"]

    for name in (
        "CategoryAdmin",
        "PriorityAdmin",
        "SlaRuleAdmin",
        "SlaMatrixResponse",
        "SlaBatchResponse",
        "ConfigHistoryEntry",
        "DeleteResponse",
    ):
        expected = _required_fields(contract[name], contract)
        actual_properties = set(application[name].get("properties", {}))
        for part in application[name].get("allOf", []):
            actual_properties.update(part.get("properties", {}))
        assert expected <= actual_properties, (name, sorted(expected - actual_properties))

    for name in (
        "CategoryAdmin",
        "PriorityAdmin",
        "DeleteResponse",
        "SlaRuleAdmin",
        "SlaMatrixResponse",
        "SlaBatchResponse",
        "ConfigHistoryEntry",
    ):
        assert _required_fields(contract[name], contract) == _required_fields(
            application[name], application
        ), name


def _non_admin_request_kwargs(method: str, path: str, headers: dict) -> dict:
    kwargs = {"headers": headers}
    if method != "post":
        return kwargs
    if path == "/api/v1/admin/categories":
        kwargs["json"] = {"name": "Prueba"}
    elif path == "/api/v1/admin/priorities":
        kwargs["json"] = {"name": "Prueba", "level": 1, "base_hours": "8.00"}
    elif path.endswith("/updates") or path.endswith("/deletion"):
        kwargs["json"] = {"expected_revision": 1}
    elif path == "/api/v1/admin/sla-rules/batch":
        kwargs["json"] = {
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": "00000000-0000-0000-0000-000000000001",
                    "priority_id": "00000000-0000-0000-0000-000000000002",
                    "hours": "8.00",
                }
            ]
        }
    elif path.endswith("/retirement"):
        kwargs["json"] = {
            "expected_rule_id": "00000000-0000-0000-0000-000000000003"
        }
    return kwargs


def test_non_admin_cannot_access_contract_endpoints(
    client: TestClient, auth, seeded
) -> None:
    entity_id = "00000000-0000-0000-0000-000000000001"
    for role_name, user in seeded.users.items():
        if role_name == "admin":
            continue
        for path, operations in _contract()["paths"].items():
            resolved = (
                path.replace("{category_id}", entity_id)
                .replace("{priority_id}", entity_id)
                .replace("{rule_id}", entity_id)
            )
            for method in operations:
                if method.startswith("x-"):
                    continue
                response = client.request(
                    method.upper(),
                    resolved,
                    **_non_admin_request_kwargs(method, path, auth(user)),
                )
                assert response.status_code == 403, (role_name, method, path)
                body = response.json()
                assert set(body) == {"detail"}
                assert set(body["detail"]) == {"code", "message"}
                assert body["detail"]["code"] == "forbidden"
                assert body["detail"]["message"] == ADMIN_FORBIDDEN_MESSAGE


def test_contract_enums_and_operation_discriminators_match_the_app() -> None:
    contract_schemas = _contract()["components"]["schemas"]
    application_schemas = app.openapi()["components"]["schemas"]

    for name, enum in (
        ("ConfigEntityType", ConfigEntityType),
        ("ConfigAction", ConfigAction),
    ):
        expected = {item.value for item in enum}
        assert set(contract_schemas[name]["enum"]) == expected
        assert set(application_schemas[name]["enum"]) == expected

    for name, operation in (("SlaUpsertChange", "upsert"), ("SlaRetireChange", "retire")):
        assert contract_schemas[name]["properties"]["operation"]["enum"] == [operation]
        assert application_schemas[name]["properties"]["operation"]["const"] == operation


def test_contract_patterns_and_formats_are_honored_at_runtime(
    client: TestClient, admin_headers
) -> None:
    contract_schemas = _contract()["components"]["schemas"]
    application_schemas = app.openapi()["components"]["schemas"]
    color_schema = contract_schemas["PriorityCreateRequest"]["properties"]["color"]
    hours_schema = contract_schemas["PriorityCreateRequest"]["properties"]["base_hours"]

    color_pattern = color_schema["pattern"]
    hours_pattern = hours_schema["pattern"]
    assert color_pattern == r"^#[0-9A-Fa-f]{6}$"
    assert (
        color_pattern
        == application_schemas["PriorityCreateRequest"]["properties"]["color"]["anyOf"][
            0
        ]["pattern"]
    )
    assert contract_schemas["SlaUpsertChange"]["properties"]["hours"]["pattern"] == (
        hours_pattern
    )

    created = client.post(
        "/api/v1/admin/priorities",
        json={
            "name": "Patrón",
            "level": 2,
            "base_hours": "8.00",
            "color": "#A1b2C3",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert re.fullmatch(hours_pattern, created.json()["base_hours"])
    assert re.fullmatch(color_pattern, created.json()["color"])

    for invalid in (
        {"name": "Sin patrón", "level": 3, "base_hours": "1.234"},
        {"name": "Color inválido", "level": 4, "base_hours": "8.00", "color": "123456"},
    ):
        rejected = client.post(
            "/api/v1/admin/priorities", json=invalid, headers=admin_headers
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "invalid_request"

    assert (
        contract_schemas["ConfigurationVersionRef"]["properties"]["created_at"][
            "format"
        ]
        == "date-time"
    )
    assert (
        contract_schemas["ConfigHistoryEntry"]["properties"]["occurred_at"]["format"]
        == "date-time"
    )
    created_category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Histórico contrato"},
        headers=admin_headers,
    )
    assert created_category.status_code == 201, created_category.text
    history = client.get("/api/v1/admin/config-history", headers=admin_headers)
    assert history.status_code == 200, history.text
    entry = history.json()["items"][0]
    for value in (
        entry["configuration_version"]["created_at"],
        entry["occurred_at"],
    ):
        datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_contract_error_responses_match_stable_runtime_codes(
    client: TestClient, admin_headers, auth, seeded
) -> None:
    contract = _contract()
    schemas = contract["components"]["schemas"]
    api_error = schemas["ApiError"]
    assert set(api_error["required"]) == {"detail"}
    assert set(api_error["properties"]["detail"]["required"]) == {"code", "message"}
    assert api_error["x-configuration-error-codes"] == CONFIGURATION_ERROR_MESSAGES
    code_enum = set(api_error["properties"]["detail"]["properties"]["code"]["enum"])
    assert set(CONFIGURATION_ERROR_MESSAGES) <= code_enum

    for operations in contract["paths"].values():
        for method, operation in operations.items():
            if method.startswith("x-"):
                continue
            for status in ("401", "403", "404", "409", "422"):
                response = operation["responses"].get(status)
                if response is None:
                    continue
                name = response["$ref"].split("/")[-1]
                assert contract["components"]["responses"][name]["content"][
                    "application/json"
                ]["schema"]["$ref"] == "#/components/schemas/ApiError"

    forbidden = client.get(
        "/api/v1/admin/categories", headers=auth(seeded.users["a"])
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "forbidden"
    assert forbidden.json()["detail"]["message"] == ADMIN_FORBIDDEN_MESSAGE

    invalid = client.post(
        "/api/v1/admin/categories", json={"name": "   "}, headers=admin_headers
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_request"

    created = client.post(
        "/api/v1/admin/categories",
        json={"name": "Conflicto"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    payload = {
        "expected_revision": created.json()["revision"],
        "name": "Conflicto actualizado",
    }
    url = f"/api/v1/admin/categories/{created.json()['id']}/updates"
    assert client.post(url, json=payload, headers=admin_headers).status_code == 200
    stale = client.post(url, json=payload, headers=admin_headers)
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_configuration"
    assert stale.json()["detail"]["message"] == CONFIGURATION_ERROR_MESSAGES[
        "stale_configuration"
    ]


def test_matrix_refs_document_and_return_is_active(
    client: TestClient, admin_headers
) -> None:
    schemas = _contract()["components"]["schemas"]
    for name in ("CategoryRef", "PriorityRef"):
        assert "is_active" in schemas[name]["properties"]
        assert "is_active" in schemas[name]["required"]

    category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Ref activa"},
        headers=admin_headers,
    )
    assert category.status_code == 201, category.text
    priority = client.post(
        "/api/v1/admin/priorities",
        json={"name": "Ref nivel 1", "level": 1, "base_hours": "8.00"},
        headers=admin_headers,
    )
    assert priority.status_code == 201, priority.text
    rule = client.post(
        "/api/v1/admin/sla-rules/batch",
        json={
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": category.json()["id"],
                    "priority_id": priority.json()["id"],
                    "hours": "6.00",
                    "expected_rule_id": None,
                }
            ]
        },
        headers=admin_headers,
    )
    assert rule.status_code == 200, rule.text

    other_category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Ref activa 2"},
        headers=admin_headers,
    )
    assert other_category.status_code == 201, other_category.text

    category_id = category.json()["id"]
    deactivated = client.post(
        f"/api/v1/admin/categories/{category_id}/updates",
        json={
            "expected_revision": category.json()["revision"],
            "is_active": False,
            "replacement_default_id": other_category.json()["id"],
        },
        headers=admin_headers,
    )
    assert deactivated.status_code == 200, deactivated.text

    matrix = client.get("/api/v1/admin/sla-rules", headers=admin_headers)
    assert matrix.status_code == 200, matrix.text
    payload = matrix.json()
    refs = list(payload["combinations"]["categories"])
    refs += list(payload["combinations"]["priorities"])
    for item in payload["items"]:
        refs.extend((item["category"], item["priority"]))
    assert refs
    for ref in refs:
        assert isinstance(ref["is_active"], bool)
    assert any(
        item["category"]["id"] == category_id
        and item["category"]["is_active"] is False
        for item in payload["items"]
    )
