"""Contrato OpenAPI de HU-01: catálogos, sugerencia y creación de tickets."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Category, Priority, User, UserRole

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-crear-ticket"
    / "contracts"
    / "openapi.yaml"
)
PNG = b"\x89PNG\r\n\x1a\n" + b"contenido"


@pytest.fixture()
def catalogs(db: Session) -> SimpleNamespace:
    user = User(
        id=uuid4(),
        name="Solicitante",
        email="solicitante@example.com",
        role=UserRole.usuario,
        is_active=True,
    )
    red = Category(
        name="Red",
        keywords=["vpn", "wifi"],
        sort_order=10,
        is_active=True,
    )
    media = Priority(
        name="Media",
        level=3,
        color="#ca8a04",
        base_hours="24.00",
        is_default=True,
        is_active=True,
    )
    db.add_all([user, red, media])
    db.commit()
    return SimpleNamespace(user=user, red=red, media=media)


@pytest.fixture()
def attachments_dir(tmp_path, monkeypatch):
    directory = tmp_path / "attachments"
    monkeypatch.setattr(get_settings(), "attachments_dir", directory)
    return directory


def _load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _validator(spec: dict, schema_name: str) -> Draft202012Validator:
    document = {
        "components": spec["components"],
        "$ref": f"#/components/schemas/{schema_name}",
    }
    return Draft202012Validator(document)


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "title": "No funciona la VPN",
        "description": "No puedo conectar desde ayer por la tarde.",
    }
    data.update(overrides)
    return data


def test_contract_declares_hu01_paths_and_schemas() -> None:
    spec = _load_contract()
    assert spec["openapi"] == "3.0.3"
    paths = spec["paths"]
    assert "/api/v1/priorities" in paths
    assert "/api/v1/suggestions" in paths
    assert "/api/v1/tickets" in paths
    for schema in (
        "Priority",
        "Category",
        "User",
        "Attachment",
        "SuggestionRequest",
        "SuggestionResponse",
        "Ticket",
        "ErrorResponse",
    ):
        assert schema in spec["components"]["schemas"]


def test_create_ticket_response_matches_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    spec = _load_contract()
    response = client.post(
        "/api/v1/tickets",
        data=_payload(),
        files={"attachments": ("captura.png", PNG, "image/png")},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 201
    body = response.json()
    _validator(spec, "Ticket").validate(body)
    assert body["duplicate"] is False
    assert len(body["attachments"]) == 1


def test_duplicate_response_matches_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    spec = _load_contract()
    headers = auth(catalogs.user)
    client.post("/api/v1/tickets", data=_payload(), headers=headers)
    response = client.post("/api/v1/tickets", data=_payload(), headers=headers)

    assert response.status_code == 200
    body = response.json()
    _validator(spec, "Ticket").validate(body)
    assert body["duplicate"] is True


def test_priorities_response_matches_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
) -> None:
    spec = _load_contract()
    response = client.get("/api/v1/priorities", headers=auth(catalogs.user))

    assert response.status_code == 200
    _validator(spec, "Priority").validate(response.json()[0])


def test_suggestion_response_matches_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
) -> None:
    spec = _load_contract()
    response = client.post(
        "/api/v1/suggestions",
        json={"title": "No funciona la VPN", "description": "Sin conexión."},
        headers=auth(catalogs.user),
    )

    assert response.status_code == 200
    _validator(spec, "SuggestionResponse").validate(response.json())


def test_error_responses_match_contract(
    client: TestClient,
    catalogs: SimpleNamespace,
    auth,
    attachments_dir,
) -> None:
    spec = _load_contract()
    unauthorized = client.post(
        "/api/v1/tickets",
        data=_payload(),
        headers=auth(catalogs.user, secret="otro-secreto"),
    )
    invalid = client.post(
        "/api/v1/tickets",
        data=_payload(title="abc"),
        headers=auth(catalogs.user),
    )

    assert unauthorized.status_code in (401, 403)
    assert invalid.status_code == 422
    _validator(spec, "ErrorResponse").validate(unauthorized.json())
    _validator(spec, "ErrorResponse").validate(invalid.json())
