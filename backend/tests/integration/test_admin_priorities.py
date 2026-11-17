from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Priority


def _create(
    client: TestClient,
    headers,
    *,
    name: str,
    level: int,
    base_hours: str = "8.00",
    **extra,
):
    return client.post(
        "/api/v1/admin/priorities",
        json={
            "name": name,
            "level": level,
            "base_hours": base_hours,
            **extra,
        },
        headers=headers,
    )


def test_priority_level_is_unique_only_when_active(
    client: TestClient, db: Session, admin_headers
) -> None:
    first = _create(client, admin_headers, name="Crítica", level=1)
    assert first.status_code == 201
    assert first.json()["is_default"] is True

    duplicate = _create(client, admin_headers, name="Otra crítica", level=1)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_priority_level"

    second = _create(client, admin_headers, name="Alta", level=2)
    assert second.status_code == 201
    second_id = second.json()["id"]
    revision = second.json()["revision"]

    deactivated = client.post(
        f"/api/v1/admin/priorities/{second_id}/updates",
        json={"expected_revision": revision, "is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200

    replacement = _create(client, admin_headers, name="Planificada", level=2)
    assert replacement.status_code == 201

    reactivated = client.post(
        f"/api/v1/admin/priorities/{second_id}/updates",
        json={
            "expected_revision": deactivated.json()["revision"],
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert reactivated.status_code == 409
    assert reactivated.json()["detail"]["code"] == "duplicate_priority_level"


def test_priority_fields_are_validated(
    client: TestClient, admin_headers
) -> None:
    invalid_color = _create(
        client,
        admin_headers,
        name="Color",
        level=1,
        color="red",
    )
    assert invalid_color.status_code == 422

    invalid_hours = _create(
        client,
        admin_headers,
        name="Horas",
        level=1,
        base_hours="0",
    )
    assert invalid_hours.status_code == 422

    too_precise = _create(
        client,
        admin_headers,
        name="Precisión",
        level=1,
        base_hours="1.234",
    )
    assert too_precise.status_code == 422


def test_default_replacement_and_last_active_priority(
    client: TestClient, db: Session, admin_headers
) -> None:
    current = _create(client, admin_headers, name="Media", level=3)
    assert current.status_code == 201
    current_id = current.json()["id"]
    revision = current.json()["revision"]
    replacement = _create(client, admin_headers, name="Baja", level=4)
    assert replacement.status_code == 201

    missing = client.post(
        f"/api/v1/admin/priorities/{current_id}/updates",
        json={"expected_revision": revision, "is_active": False},
        headers=admin_headers,
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "default_replacement_required"

    moved = client.post(
        f"/api/v1/admin/priorities/{current_id}/updates",
        json={
            "expected_revision": revision,
            "is_active": False,
            "replacement_default_id": replacement.json()["id"],
        },
        headers=admin_headers,
    )
    assert moved.status_code == 200

    db.refresh(db.get(Priority, __import__("uuid").UUID(replacement.json()["id"])))
    last = client.post(
        f"/api/v1/admin/priorities/{replacement.json()['id']}/updates",
        json={
            "expected_revision": replacement.json()["revision"],
            "is_active": False,
        },
        headers=admin_headers,
    )
    assert last.status_code == 409
    assert last.json()["detail"]["code"] == "last_active_catalog_item"


def test_system_priority_cannot_be_updated_or_deleted(
    client: TestClient, db: Session, admin_headers
) -> None:
    system = Priority(
        name="Sin clasificar",
        level=4,
        base_hours="72.00",
        is_system=True,
        is_active=True,
        revision=1,
    )
    db.add(system)
    db.commit()

    updated = client.post(
        f"/api/v1/admin/priorities/{system.id}/updates",
        json={"expected_revision": 1, "name": "Otra"},
        headers=admin_headers,
    )
    assert updated.status_code == 409
    assert updated.json()["detail"]["code"] == "system_catalog_item"

    deleted = client.post(
        f"/api/v1/admin/priorities/{system.id}/deletion",
        json={"expected_revision": 1},
        headers=admin_headers,
    )
    assert deleted.status_code == 409
    assert deleted.json()["detail"]["code"] == "system_catalog_item"
