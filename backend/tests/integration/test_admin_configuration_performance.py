from __future__ import annotations

import math
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import IS_SQLITE

pytestmark = pytest.mark.skipif(
    IS_SQLITE, reason="El rendimiento real requiere TEST_DATABASE_URL de PostgreSQL"
)

READ_THRESHOLD_MS = 300
BATCH_THRESHOLD_MS = 400
TICKET_THRESHOLD_MS = 300


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _measure(call, samples: int = 15) -> float:
    values = []
    for _ in range(samples):
        started = perf_counter()
        response = call()
        values.append((perf_counter() - started) * 1000)
        assert response.status_code in (200, 201), response.text
    return _p95(values)


def _catalog(client: TestClient, admin_headers, user_headers) -> tuple[str, str]:
    category = client.post(
        "/api/v1/admin/categories",
        json={"name": "Rendimiento"},
        headers=admin_headers,
    )
    assert category.status_code == 201
    priority = client.post(
        "/api/v1/admin/priorities",
        json={
            "name": "Rendimiento",
            "level": 1,
            "base_hours": "8.00",
        },
        headers=admin_headers,
    )
    assert priority.status_code == 201
    return category.json()["id"], priority.json()["id"]


def test_admin_endpoints_cumplen_umbrales(
    client: TestClient, db: Session, admin_headers, auth, admin_user
) -> None:
    category_id, priority_id = _catalog(client, admin_headers, auth(admin_user))
    user_headers = auth(admin_user)

    reads = {
        "categories": _measure(
            lambda: client.get("/api/v1/admin/categories", headers=admin_headers)
        ),
        "sla_rules": _measure(
            lambda: client.get("/api/v1/admin/sla-rules", headers=admin_headers)
        ),
        "history": _measure(
            lambda: client.get("/api/v1/admin/config-history", headers=admin_headers)
        ),
    }
    assert all(value < READ_THRESHOLD_MS for value in reads.values()), reads

    category_ids = [category_id]
    for index in range(19):
        created = client.post(
            "/api/v1/admin/categories",
            json={"name": f"Rendimiento {index}"},
            headers=admin_headers,
        )
        assert created.status_code == 201
        category_ids.append(created.json()["id"])

    changes = [
        {
            "operation": "upsert",
            "category_id": current_category_id,
            "priority_id": priority_id,
            "hours": "2.00",
            "expected_rule_id": None,
        }
        for current_category_id in category_ids
    ]

    def batch_call():
        response = client.post(
            "/api/v1/admin/sla-rules/batch",
            json={"changes": changes},
            headers=admin_headers,
        )
        if response.status_code == 200:
            current_rules = {
                (item["category"]["id"], item["priority"]["id"]): item["id"]
                for item in response.json()["items"]
            }
            for change in changes:
                change["expected_rule_id"] = current_rules[
                    (change["category_id"], change["priority_id"])
                ]
        return response

    batch_p95 = _measure(batch_call, samples=10)
    assert batch_p95 < BATCH_THRESHOLD_MS, batch_p95

    ticket_p95 = _measure(
        lambda: client.post(
            "/api/v1/tickets",
            data={
                "title": "Incidencia de rendimiento",
                "description": "Descripción suficiente para crear la incidencia.",
                "priority_id": priority_id,
                "category_id": category_id,
            },
            headers=user_headers,
        )
    )
    assert ticket_p95 < TICKET_THRESHOLD_MS, ticket_p95
