"""Pruebas del stub de autenticación de desarrollo."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import SeededQueue

LOGIN = "/api/v1/dev/login"
QUEUE = "/api/v1/me/work-queue"


def _login(client: TestClient, email: str) -> str:
    response = client.post(LOGIN, json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_dev_login_returns_a_token_that_can_read_the_queue(
    client: TestClient, seeded: SeededQueue
) -> None:
    response = client.post(LOGIN, json={"email": "tecnico.a@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "tecnico.a@example.com"
    assert body["user"]["role"] == "tecnico"

    queue = client.get(
        QUEUE, headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert queue.status_code == 200
    assert len(queue.json()["items"]) == 5


def test_dev_login_allows_testing_a_forbidden_role(
    client: TestClient, seeded: SeededQueue
) -> None:
    token = _login(client, "supervisor@example.com")

    queue = client.get(QUEUE, headers={"Authorization": f"Bearer {token}"})

    assert queue.status_code == 403
    assert queue.json()["detail"]["code"] == "forbidden"


def test_dev_login_rejects_unknown_or_inactive_users(
    client: TestClient, seeded: SeededQueue
) -> None:
    response = client.post(LOGIN, json={"email": "nadie@example.com"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "dev_user_not_found"
