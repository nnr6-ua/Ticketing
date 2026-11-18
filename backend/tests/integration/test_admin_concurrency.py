from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ConfigurationVersion, SlaRule
from tests.conftest import IS_SQLITE

pytestmark = pytest.mark.skipif(
    IS_SQLITE, reason="La concurrencia real requiere TEST_DATABASE_URL de PostgreSQL"
)


def _catalog(client: TestClient, admin_headers: dict[str, str]):
    category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Concurrencia"},
        headers=admin_headers,
    )
    assert category.status_code == 201
    priority = client.post(
        "/api/v1/admin/priorities",
        json={
            "name": "Urgente concurrente",
            "level": 1,
            "base_hours": "8.00",
        },
        headers=admin_headers,
    )
    assert priority.status_code == 201
    return category.json(), priority.json()


def _batch(category_id: str, priority_id: str, hours: str, expected_rule_id=None):
    return {
        "changes": [
            {
                "operation": "upsert",
                "category_id": category_id,
                "priority_id": priority_id,
                "hours": hours,
                "expected_rule_id": expected_rule_id,
            }
        ]
    }


def _concurrent(method: str, url: str, *, json, headers, count: int = 2):
    barrier = Barrier(count)

    def request(payload):
        with TestClient(app, raise_server_exceptions=False) as client:
            barrier.wait()
            return client.request(method, url, json=payload, headers=headers)

    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(request, json))


def test_two_admins_updating_same_category_get_stale_response(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, _ = _catalog(client, admin_headers)
    url = f"/api/v1/admin/categories/{category['id']}/updates"

    responses = _concurrent(
        "POST",
        url,
        json=[
            {"expected_revision": 1, "name": "Concurrencia A"},
            {"expected_revision": 1, "name": "Concurrencia B"},
        ],
        headers=[admin_headers, admin_headers],
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert any(
        response.json()["detail"]["code"] == "stale_configuration"
        for response in responses
        if response.status_code == 409
    )


def test_two_admins_updating_same_rule_create_single_version(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    url = "/api/v1/admin/sla-rules/batch"
    payloads = [
        _batch(category["id"], priority["id"], "2.00"),
        _batch(category["id"], priority["id"], "3.00"),
    ]

    responses = _concurrent("POST", url, json=payloads, headers=[admin_headers] * 2)

    assert sorted(response.status_code for response in responses) == [200, 409]
    versions = db.scalar(select(func.count()).select_from(ConfigurationVersion))
    rules = db.scalar(
        select(func.count()).select_from(SlaRule).where(SlaRule.valid_to_version.is_(None))
    )
    assert versions == 2
    assert rules == 1


def test_retrying_applied_batch_does_not_duplicate_rules(
    client: TestClient, db: Session, admin_headers
) -> None:
    category, priority = _catalog(client, admin_headers)
    url = "/api/v1/admin/sla-rules/batch"

    first = client.post(
        url,
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert first.status_code == 200
    rule_id = UUID(first.json()["items"][0]["id"])

    retry = client.post(
        url,
        json=_batch(category["id"], priority["id"], "2.00"),
        headers=admin_headers,
    )
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "stale_configuration"

    rules = db.scalars(select(SlaRule)).all()
    versions = db.scalars(select(ConfigurationVersion)).all()
    assert len(rules) == 1
    assert rules[0].id == rule_id
    assert [version.version for version in versions] == [1, 2]
