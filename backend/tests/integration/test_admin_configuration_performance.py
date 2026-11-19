from __future__ import annotations

import gc
import math
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.models import ConfigurationAuditEntry, ConfigurationVersion
from app.services import ticket_creation
from app.services.sla_resolution import ResolvedSla
from tests.conftest import IS_SQLITE

pytestmark = pytest.mark.skipif(
    IS_SQLITE, reason="El rendimiento real requiere TEST_DATABASE_URL de PostgreSQL"
)

READ_THRESHOLD_MS = 300
BATCH_THRESHOLD_MS = 400
TICKET_THRESHOLD_MS = 10

HISTORY_PAGE_SIZE = 25
HISTORY_ENTRIES = HISTORY_PAGE_SIZE
EXPECTED_AUDIT_ENTRIES = HISTORY_ENTRIES + 2


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _time_once(call, *, validate=None) -> float:
    started = perf_counter()
    response = call()
    elapsed = (perf_counter() - started) * 1000
    assert response.status_code in (200, 201), response.text
    if validate is not None:
        validate(response)
    return elapsed


def _measure(call, samples: int = 15, *, validate=None) -> float:
    return _p95(
        [_time_once(call, validate=validate) for _ in range(samples)]
    )


def _catalog(client: TestClient, admin_headers) -> tuple[str, str]:
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


def test_config_history_uses_occurred_at_index(
    client: TestClient, db: Session, admin_headers
) -> None:
    _catalog(client, admin_headers)
    for index in range(300):
        created = client.post(
            "/api/v1/admin/categories",
            json={"name": f"Histórico rendimiento {index}"},
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text

    statement = (
        select(ConfigurationAuditEntry)
        .options(
            joinedload(ConfigurationAuditEntry.configuration_version).joinedload(
                ConfigurationVersion.created_by
            ),
            joinedload(ConfigurationAuditEntry.actor),
        )
        .order_by(
            ConfigurationAuditEntry.occurred_at.desc(),
            ConfigurationAuditEntry.id.desc(),
        )
        .offset(0)
        .limit(HISTORY_PAGE_SIZE)
    )
    compiled = statement.compile(db.get_bind(), compile_kwargs={"literal_binds": True})
    plan_rows = db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {compiled}")).all()
    plan = "\n".join(row[0] for row in plan_rows)
    print("config_history_plan", plan)
    assert "ix_config_audit_occurred_at" in plan


def test_admin_endpoints_cumplen_umbrales(
    client: TestClient,
    db: Session,
    admin_headers,
    auth,
    admin_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    category_id, priority_id = _catalog(client, admin_headers)
    user_headers = auth(admin_user)

    category_ids = [category_id]
    for index in range(HISTORY_ENTRIES - 2):
        created = client.post(
            "/api/v1/admin/categories",
            json={"name": f"Rendimiento {index}"},
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        category_ids.append(created.json()["id"])

    history = client.get("/api/v1/admin/config-history", headers=admin_headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["items"]) == HISTORY_PAGE_SIZE
    assert history.json()["pagination"]["total_items"] == EXPECTED_AUDIT_ENTRIES

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

    changes = [
        {
            "operation": "upsert",
            "category_id": current_category_id,
            "priority_id": priority_id,
            "hours": "2.00",
            "expected_rule_id": None,
        }
        for current_category_id in category_ids[:20]
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

    baseline_payload = {
        "title": "Incidencia de línea base de rendimiento",
        "description": "Descripción suficiente para crear la incidencia de línea base.",
        "priority_id": priority_id,
        "category_id": category_id,
    }
    baseline_version_id = db.scalar(
        select(ConfigurationVersion.id)
        .order_by(ConfigurationVersion.version.desc())
        .limit(1)
    )
    assert baseline_version_id is not None

    legacy_resolution_samples: list[float] = []
    current_resolution_samples: list[float] = []

    def legacy_resolution(_session, _category, priority):
        started = perf_counter()
        result = (
            ResolvedSla(
                hours=Decimal(priority.base_hours).quantize(Decimal("0.01")),
                priority_level=priority.level,
                source="priority_base",
                rule_id=None,
                config_version_id=baseline_version_id,
            ),
            baseline_version_id,
            1,
        )
        legacy_resolution_samples.append((perf_counter() - started) * 1000)
        return result

    def legacy_ticket_call():
        return client.post(
            "/api/v1/tickets",
            data={
                **baseline_payload,
                "title": f"Línea base de rendimiento {uuid4()}",
            },
            headers=user_headers,
        )

    original_resolution = ticket_creation._resolve_sla_snapshot

    def current_resolution(session, category, priority):
        started = perf_counter()
        result = original_resolution(session, category, priority)
        current_resolution_samples.append((perf_counter() - started) * 1000)
        return result

    def ticket_call():
        return client.post(
            "/api/v1/tickets",
            data={
                **baseline_payload,
                "title": f"Incidencia de rendimiento {uuid4()}",
            },
            headers=user_headers,
        )

    def validate_ticket(response) -> None:
        assert response.json()["duplicate"] is False
        assert response.json()["sla_config_version_id"] is not None

    baseline_samples: list[float] = []
    ticket_samples: list[float] = []
    deltas: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(ticket_creation, "_resolve_sla_snapshot", legacy_resolution)
            _time_once(legacy_ticket_call, validate=validate_ticket)
            patcher.setattr(ticket_creation, "_resolve_sla_snapshot", current_resolution)
            _time_once(ticket_call, validate=validate_ticket)
            legacy_resolution_samples.clear()
            current_resolution_samples.clear()

            for _ in range(31):
                patcher.setattr(
                    ticket_creation, "_resolve_sla_snapshot", legacy_resolution
                )
                baseline = _time_once(legacy_ticket_call, validate=validate_ticket)
                patcher.setattr(
                    ticket_creation, "_resolve_sla_snapshot", current_resolution
                )
                current = _time_once(ticket_call, validate=validate_ticket)
                baseline_samples.append(baseline)
                ticket_samples.append(current)
                deltas.append(
                    current_resolution_samples[-1] - legacy_resolution_samples[-1]
                )
    finally:
        if gc_was_enabled:
            gc.enable()

    baseline_p95 = _p95(baseline_samples)
    ticket_p95 = _p95(ticket_samples)
    ticket_overhead_ms = _p95(deltas)
    print(
        "p95_ms",
        {
            **reads,
            "batch": batch_p95,
            "ticket_base": baseline_p95,
            "ticket": ticket_p95,
            "ticket_incremento": ticket_overhead_ms,
        },
    )
    assert ticket_overhead_ms < TICKET_THRESHOLD_MS, (
        baseline_p95,
        ticket_p95,
        ticket_overhead_ms,
    )
