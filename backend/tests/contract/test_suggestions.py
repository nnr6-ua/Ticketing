from fastapi.testclient import TestClient

HEADERS = {"X-Employee-Id": "1"}


def test_suggests_category_and_priority(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suggestions",
        json={
            "title": "No funciona la VPN urgente",
            "description": "No puedo conectar desde ayer por la tarde.",
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"]["name"] == "Red y conectividad"
    assert body["priority"]["name"] == "Crítica"
    assert body["category_is_fallback"] is False
    assert body["priority_is_fallback"] is False


def test_suggestion_falls_back_to_defaults(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suggestions",
        json={"title": "zzz", "description": "zzz"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"]["name"] == "Otros"
    assert body["priority"]["name"] == "Media"
    assert body["category_is_fallback"] is True
    assert body["priority_is_fallback"] is True


def test_suggestion_accepts_empty_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suggestions",
        json={"title": "", "description": ""},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["category"]["name"] == "Otros"


def test_requires_employee_header(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suggestions",
        json={"title": "No funciona la VPN", "description": "No puedo conectar."},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_required"
