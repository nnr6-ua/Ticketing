from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserRole


@pytest.fixture()
def users(db: Session) -> dict[str, User]:
    result: dict[str, User] = {}
    for role in (UserRole.usuario, UserRole.tecnico, UserRole.supervisor):
        user = User(
            id=uuid.uuid4(),
            name=role.value.title(),
            email=f"{role.value}.auth@example.com",
            role=role,
            is_active=True,
        )
        db.add(user)
        result[role.value] = user
    db.commit()
    return result


def _assert_forbidden(response, message: str) -> None:
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["code"] == "forbidden"
    assert body["detail"]["message"] == message


def test_admin_endpoints_require_authentication(client: TestClient) -> None:
    for path in (
        "/api/v1/admin/categories",
        "/api/v1/admin/priorities",
        "/api/v1/admin/sla-rules",
        "/api/v1/admin/config-history",
    ):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "not_authenticated"


def test_non_admin_roles_receive_403(
    client: TestClient, users: dict[str, User], auth
) -> None:
    expected = "Esta configuración está disponible solo para administración."
    for user in users.values():
        response = client.get("/api/v1/admin/categories", headers=auth(user))
        _assert_forbidden(response, expected)

    response = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red"},
        headers=auth(users["tecnico"]),
    )
    _assert_forbidden(response, expected)


def test_admin_can_read_and_create_categories(
    client: TestClient, admin_headers
) -> None:
    listed = client.get("/api/v1/admin/categories", headers=admin_headers)
    assert listed.status_code == 200

    created = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Red"
