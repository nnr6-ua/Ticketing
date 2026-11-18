"""Pruebas de contrato del dashboard de SLA contra el OpenAPI de HU-07."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import jsonschema
import pytest
import yaml

from tests.integration._hu07 import API, OPTIONS_API, assert_vary_authorization

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "007-dashboard-cumplimiento-sla"
    / "contracts"
    / "sla-dashboard.openapi.yaml"
)


@pytest.fixture(scope="module")
def contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    def to_json_schema(node):
        """Traduce el `nullable` de OpenAPI 3.0 a JSON Schema estándar."""

        if isinstance(node, dict):
            converted = {key: to_json_schema(value) for key, value in node.items()}
            nullable = converted.pop("nullable", False)
            if nullable and "type" in converted:
                base = converted["type"]
                converted["type"] = [base, "null"] if isinstance(base, str) else base
            elif nullable and "allOf" in converted:
                # En OAS 3.0 `nullable` junto a `$ref` no se respeta; se expresa
                # con `allOf` y se traduce a `anyOf([...ref, null])` para JSON Schema.
                converted["anyOf"] = [
                    *converted.pop("allOf"),
                    {"type": "null"},
                ]
            return converted
        if isinstance(node, list):
            return [to_json_schema(item) for item in node]
        return node

    return to_json_schema(document)


def _root_schema(contract: dict, name: str) -> dict:
    return {
        "$ref": f"#/components/schemas/{name}",
        "components": contract["components"],
    }


@pytest.fixture()
def dashboard_response(client, dashboard_seed):
    response = client.get(API, headers=dashboard_seed.supervisor_headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_response_matches_openapi_contract(contract, dashboard_response):
    jsonschema.validate(
        instance=dashboard_response,
        schema=_root_schema(contract, "SlaDashboardResponse"),
    )


def test_options_response_matches_openapi_contract(contract, client, dashboard_seed):
    response = client.get(OPTIONS_API, headers=dashboard_seed.supervisor_headers)
    assert response.status_code == 200, response.text
    jsonschema.validate(
        instance=response.json(),
        schema=_root_schema(contract, "SlaDashboardOptions"),
    )


def test_matrix_and_totals_entries_match_contract(contract, dashboard_response):
    matrix_schema = _root_schema(contract, "MatrixRow")
    totals_schema = _root_schema(contract, "TotalsEntry")
    ranking_schema = _root_schema(contract, "RankingEntry")

    for row in dashboard_response["data"]["matrix"]:
        jsonschema.validate(instance=row, schema=matrix_schema)
    for row in dashboard_response["data"]["priority_totals"]:
        jsonschema.validate(instance=row, schema=totals_schema)
    for row in dashboard_response["data"]["category_totals"]:
        jsonschema.validate(instance=row, schema=totals_schema)
    for row in dashboard_response["data"]["ranking"]["technicians"]:
        jsonschema.validate(instance=row, schema=ranking_schema)


def test_required_fields_and_nullable_technician_id(dashboard_response):
    summary = dashboard_response["data"]["summary"]
    for key in (
        "ticket_count",
        "no_sla_count",
        "attended_with_sla",
        "on_time",
        "compliance_pct",
        "avg_response_seconds",
        "overdue_count",
        "semaphore",
    ):
        assert key in summary

    unassigned = dashboard_response["data"]["ranking"]["unassigned"]
    assert unassigned is not None
    assert unassigned["technician_id"] is None
    assert unassigned["is_active"] is None
    assert unassigned["team"] is None


def test_unassigned_schema_admits_null(contract):
    response_schema = contract["components"]["schemas"]["SlaDashboardResponse"]
    unassigned = response_schema["properties"]["data"]["properties"]["ranking"][
        "properties"
    ]["unassigned"]
    schema = {**unassigned, "components": contract["components"]}

    jsonschema.validate(instance=None, schema=schema)
    jsonschema.validate(
        instance={
            "technician_id": None,
            "technician_name": "Sin asignar",
            "team": None,
            "is_active": None,
            "overdue_count": 1,
            "avg_delay_seconds": 60.0,
        },
        schema=schema,
    )


def test_response_without_unassigned_matches_contract(
    contract, client, dashboard_seed
):
    madrid_day = dashboard_seed.now.date()
    params = {
        "desde": (madrid_day - timedelta(days=1)).isoformat(),
        "hasta": madrid_day.isoformat(),
    }
    response = client.get(
        API, headers=dashboard_seed.supervisor_headers, params=params
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["ranking"]["unassigned"] is None
    jsonschema.validate(
        instance=body, schema=_root_schema(contract, "SlaDashboardResponse")
    )


def test_thresholds_and_scope_are_contract_values(dashboard_response):
    thresholds = dashboard_response["meta"]["thresholds"]
    assert thresholds == {"green_pct": 90.0, "amber_pct": 70.0}

    for row in dashboard_response["data"]["priority_totals"]:
        assert row["scope"] == "priority"
    for row in dashboard_response["data"]["category_totals"]:
        assert row["scope"] == "category"


def test_priority_level_is_between_one_and_four(dashboard_response):
    for row in dashboard_response["data"]["matrix"]:
        assert 1 <= row["priority_level"] <= 4


def _declared_response(contract: dict, path: str, status: str) -> dict:
    response = contract["paths"][path]["get"]["responses"][status]
    if "$ref" in response:
        name = response["$ref"].rsplit("/", 1)[-1]
        response = contract["components"]["responses"][name]
    return response


@pytest.mark.parametrize("path", ["/sla-dashboard", "/sla-dashboard/options"])
@pytest.mark.parametrize("status", ["200", "401", "403", "422"])
def test_contract_declares_vary_authorization(contract, path, status):
    headers = _declared_response(contract, path, status).get("headers", {})

    assert "Vary" in headers, f"{path} {status} no declara Vary"
    assert headers["Vary"]["description"].strip('"') == "Authorization"


def test_vary_authorization_is_sent_on_success(client, dashboard_seed):
    for url in (API, OPTIONS_API):
        response = client.get(url, headers=dashboard_seed.supervisor_headers)

        assert response.status_code == 200, response.text
        assert_vary_authorization(response)
        assert response.headers["Cache-Control"] == "no-store"


def test_vary_authorization_is_sent_on_errors(client, dashboard_seed):
    unauthenticated = client.get(API)
    forbidden = client.get(
        API, headers=dashboard_seed.headers_for("tecnico_a")
    )
    invalid = client.get(
        API,
        headers=dashboard_seed.supervisor_headers,
        params={"desde": "2026-11-10", "hasta": "2026-11-01"},
    )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert invalid.status_code == 422
    for response in (unauthenticated, forbidden, invalid):
        assert_vary_authorization(response)
        assert response.headers["Cache-Control"] == "no-store"
