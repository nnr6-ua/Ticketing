from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ADMIN_FORBIDDEN_MESSAGE
from app.models import User, UserRole

_CATEGORY_ID = uuid.uuid4()
_PRIORITY_ID = uuid.uuid4()
_RULE_ID = uuid.uuid4()

ADMIN_ROUTES = (
    ("GET", "/api/v1/admin/categories", None),
    (
        "POST",
        "/api/v1/admin/categories",
        {"name": "Prueba", "is_default": False},
    ),
    (
        "POST",
        f"/api/v1/admin/categories/{_CATEGORY_ID}/updates",
        {"expected_revision": 1},
    ),
    (
        "POST",
        f"/api/v1/admin/categories/{_CATEGORY_ID}/deletion",
        {"expected_revision": 1},
    ),
    ("GET", "/api/v1/admin/priorities", None),
    (
        "POST",
        "/api/v1/admin/priorities",
        {"name": "Prueba", "level": 1, "base_hours": "8.00"},
    ),
    (
        "POST",
        f"/api/v1/admin/priorities/{_PRIORITY_ID}/updates",
        {"expected_revision": 1},
    ),
    (
        "POST",
        f"/api/v1/admin/priorities/{_PRIORITY_ID}/deletion",
        {"expected_revision": 1},
    ),
    ("GET", "/api/v1/admin/sla-rules", None),
    (
        "POST",
        "/api/v1/admin/sla-rules/batch",
        {
            "changes": [
                {
                    "operation": "upsert",
                    "category_id": str(_CATEGORY_ID),
                    "priority_id": str(_PRIORITY_ID),
                    "hours": "8.00",
                }
            ]
        },
    ),
    (
        "POST",
        f"/api/v1/admin/sla-rules/{_RULE_ID}/retirement",
        {"expected_rule_id": str(_RULE_ID)},
    ),
    ("GET", "/api/v1/admin/config-history", None),
)


def _assert_no_configuration_data(response) -> None:
    assert set(response.json()) == {"detail"}
    assert set(response.json()["detail"]) == {"code", "message"}


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


def test_all_admin_routes_require_authentication(client: TestClient) -> None:
    for method, path, payload in ADMIN_ROUTES:
        kwargs = {}
        if payload is not None:
            kwargs["json"] = payload
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401, (method, path)
        assert response.json()["detail"]["code"] == "not_authenticated"
        _assert_no_configuration_data(response)


def test_all_admin_routes_forbid_non_admin_roles_without_data(
    client: TestClient, users: dict[str, User], auth
) -> None:
    for method, path, payload in ADMIN_ROUTES:
        for user in users.values():
            kwargs = {"headers": auth(user)}
            if payload is not None:
                kwargs["json"] = payload
            response = client.request(method, path, **kwargs)
            assert response.status_code == 403, (method, path, user.role)
            body = response.json()["detail"]
            assert body["code"] == "forbidden"
            assert body["message"] == ADMIN_FORBIDDEN_MESSAGE
            _assert_no_configuration_data(response)


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
