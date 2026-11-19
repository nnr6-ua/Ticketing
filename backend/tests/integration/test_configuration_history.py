from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _history(client: TestClient, headers, **params):
    response = client.get(
        "/api/v1/admin/config-history",
        params=params,
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def test_history_is_append_only_and_keeps_actor_and_values(
    client: TestClient, admin_headers, admin_user
) -> None:
    created = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red", "description": "Conectividad"},
        headers=admin_headers,
    )
    category_id = created.json()["id"]

    updated = client.post(
        f"/api/v1/admin/categories/{category_id}/updates",
        json={
            "expected_revision": created.json()["revision"],
            "description": "Conectividad y VPN",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200

    body = _history(client, admin_headers)
    assert body["pagination"]["total_items"] == 3
    first = body["items"][0]
    assert first["entity_id"] == category_id
    assert first["actor"]["id"] == str(admin_user.id)
    assert first["actor"]["name"] == admin_user.name
    assert first["previous_values"]["description"] == "Conectividad"
    assert first["new_values"]["description"] == "Conectividad y VPN"
    assert first["summary"]

    write_attempt = client.post(
        "/api/v1/admin/config-history",
        json={},
        headers=admin_headers,
    )
    assert write_attempt.status_code == 405


def test_history_filters_and_orders_descending(
    client: TestClient, admin_headers
) -> None:
    created = client.post(
        "/api/v1/admin/categories",
        json={"name": "Red"},
        headers=admin_headers,
    )
    category_id = created.json()["id"]
    revision = created.json()["revision"]

    client.post(
        f"/api/v1/admin/categories/{category_id}/updates",
        json={"expected_revision": revision, "description": "Uno"},
        headers=admin_headers,
    )

    all_entries = _history(client, admin_headers, entity_type="category")
    timestamps = [
        datetime.fromisoformat(item["occurred_at"].replace("Z", "+00:00"))
        for item in all_entries["items"]
    ]
    assert timestamps == sorted(timestamps, reverse=True)

    by_entity = _history(
        client,
        admin_headers,
        entity_type="category",
        entity_id=category_id,
    )
    assert by_entity["pagination"]["total_items"] == 3

    by_action = _history(
        client,
        admin_headers,
        action="create",
        entity_id=category_id,
    )
    assert by_action["pagination"]["total_items"] == 1
    assert by_action["items"][0]["action"] == "create"

    version_id = all_entries["items"][0]["configuration_version"]["id"]
    by_version = _history(
        client,
        admin_headers,
        configuration_version_id=version_id,
    )
    assert by_version["pagination"]["total_items"] == 1
    assert by_version["items"][0]["configuration_version"]["id"] == version_id


def test_history_date_filters_and_pagination(
    client: TestClient, admin_headers
) -> None:
    for index in range(3):
        response = client.post(
            "/api/v1/admin/categories",
            json={"name": f"Categoría {index}"},
            headers=admin_headers,
        )
        assert response.status_code == 201

    page = _history(client, admin_headers, page=2, page_size=1)
    assert page["pagination"]["page"] == 2
    assert page["pagination"]["page_size"] == 1
    assert page["pagination"]["total_items"] == 4
    assert page["pagination"]["total_pages"] == 4
    assert page["pagination"]["has_next"] is True
    assert page["pagination"]["has_previous"] is True

    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(hours=1)).isoformat()
    to_date = (now + timedelta(hours=1)).isoformat()
    filtered = _history(
        client,
        admin_headers,
        **{"from": from_date, "to": to_date},
    )
    assert filtered["pagination"]["total_items"] == 4

    future = (now + timedelta(days=1)).isoformat()
    empty = _history(client, admin_headers, **{"from": future})
    assert empty["pagination"]["total_items"] == 0
    assert empty["pagination"]["total_pages"] == 0
    assert empty["items"] == []


def test_history_date_filters_normalize_mixed_timezones(
    client: TestClient, admin_headers
) -> None:
    created = client.post(
        "/api/v1/admin/categories",
        json={"name": "Mixta"},
        headers=admin_headers,
    )
    assert created.status_code == 201

    now = datetime.now(timezone.utc)
    naive_from = (now - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    aware_to = (now + timedelta(hours=1)).isoformat()
    mixed = _history(
        client,
        admin_headers,
        **{"from": naive_from, "to": aware_to},
    )
    assert mixed["pagination"]["total_items"] >= 1

    naive_after = (now + timedelta(days=1)).replace(tzinfo=None).isoformat()
    aware_before = (now - timedelta(days=1)).isoformat()
    invalid = client.get(
        "/api/v1/admin/config-history",
        params={"from": naive_after, "to": aware_before},
        headers=admin_headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_date_range"
