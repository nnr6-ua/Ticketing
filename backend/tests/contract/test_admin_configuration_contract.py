from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app

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


def test_contract_schemas_keep_required_fields() -> None:
    contract = _contract()
    application = app.openapi()["components"]["schemas"]

    for name in (
        "CategoryAdmin",
        "PriorityAdmin",
        "SlaRuleAdmin",
        "SlaMatrixResponse",
        "SlaBatchResponse",
        "ConfigHistoryEntry",
    ):
        schema = contract["components"]["schemas"][name]
        expected = set(schema.get("required", []))
        for part in schema.get("allOf", []):
            expected.update(part.get("required", []))
        actual = set(application[name]["properties"])
        assert expected <= actual, (name, sorted(expected - actual))


def test_non_admin_cannot_access_contract_endpoints(
    client: TestClient, auth, seeded
) -> None:
    expected = "Esta configuración está disponible solo para administración."
    for path in _contract()["paths"]:
        response = client.get(path, headers=auth(seeded.users["a"]))
        assert response.status_code in {403, 405}, path
        if response.status_code == 403:
            assert response.json()["detail"]["message"] == expected
