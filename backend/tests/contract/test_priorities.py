from fastapi.testclient import TestClient

HEADERS = {"X-Employee-Id": "1"}


def test_lists_active_priorities(client: TestClient) -> None:
    response = client.get("/api/v1/priorities", headers=HEADERS)

    assert response.status_code == 200
    names = [priority["name"] for priority in response.json()]
    assert names == ["Crítica", "Alta", "Media", "Baja", "Sin clasificar"]


def test_priorities_include_level_and_color(client: TestClient) -> None:
    response = client.get("/api/v1/priorities", headers=HEADERS)

    media = next(item for item in response.json() if item["name"] == "Media")
    assert media["level"] == 3
    assert media["color"] == "#eab308"


def test_requires_employee_header(client: TestClient) -> None:
    response = client.get("/api/v1/priorities")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_required"
