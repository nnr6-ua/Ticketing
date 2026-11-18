"""Matriz de permisos de los endpoints del dashboard de SLA."""

from __future__ import annotations

import pytest

from tests.integration._hu07 import API, OPTIONS_API

FORBIDDEN_MESSAGE = "No tienes permiso para acceder a este dashboard."


@pytest.mark.parametrize("path", [API, OPTIONS_API])
def test_without_token_returns_401(client, dashboard_seed, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vary"] == "Authorization"


@pytest.mark.parametrize("role", ["tecnico_a", "usuario"])
@pytest.mark.parametrize("path", [API, OPTIONS_API])
def test_technicians_and_users_are_forbidden(client, dashboard_seed, role, path):
    response = client.get(path, headers=dashboard_seed.headers_for(role))

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "forbidden"
    assert detail["message"] == FORBIDDEN_MESSAGE
    assert "data" not in response.json()
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vary"] == "Authorization"


@pytest.mark.parametrize("role", ["supervisor", "admin"])
def test_supervisor_and_admin_have_access(client, dashboard_seed, role):
    response = client.get(API, headers=dashboard_seed.headers_for(role))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vary"] == "Authorization"


def test_response_does_not_leak_personal_data(client, dashboard_seed):
    response = client.get(API, headers=dashboard_seed.supervisor_headers)
    body = response.json()

    technician = body["data"]["ranking"]["technicians"][0]
    assert set(technician) == {
        "technician_id",
        "technician_name",
        "team",
        "is_active",
        "overdue_count",
        "avg_delay_seconds",
    }

    text = response.text
    assert "email" not in text
    assert "creator" not in text
    assert "TK-0007" not in text
