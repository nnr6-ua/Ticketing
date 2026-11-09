"""Pruebas de integración del endpoint de cola de trabajo."""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Priority, Ticket, TicketStatus, User
from app.schemas.work_queue import WorkQueueQuery
from app.services.work_queue import build_work_queue
from tests.conftest import SeededQueue

ENDPOINT = "/api/v1/me/work-queue"

A_ACTIVE_ORDER = [
    "TK-000101",
    "TK-000102",
    "TK-000103",
    "TK-000104",
    "TK-000105",
]


def get(client: TestClient, seed: SeededQueue, query: str = ""):
    return client.get(f"{ENDPOINT}{query}", headers=seed.header_for("a"))


def numbers(payload: dict) -> list[str]:
    return [item["number"] for item in payload["items"]]


# ---------------------------------------------------------------------------
# T075 · Propiedad, orden y paginación
# ---------------------------------------------------------------------------


def test_returns_only_authenticated_technician_tickets(
    seeded_client, db: Session
) -> None:
    response = get(seeded_client.client, seeded_client.seed)
    assert response.status_code == 200

    payload = response.json()
    assert numbers(payload) == A_ACTIVE_ORDER
    assert all(not number.startswith("TK-0002") for number in numbers(payload))
    assert payload["pagination"]["total_items"] == 5
    assert payload["counts"] == {"active": 5, "finalized": 2}


def test_cache_headers(seeded_client) -> None:
    response = get(seeded_client.client, seeded_client.seed)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vary"] == "Authorization"


def test_injected_technician_id_is_ignored(seeded_client) -> None:
    seed = seeded_client.seed
    response = get(
        seeded_client.client,
        seed,
        f"?technician_id={seed.users['b'].id}&assignee_id={seed.users['b'].id}",
    )
    assert response.status_code == 200
    assert numbers(response.json()) == A_ACTIVE_ORDER


def test_order_priority_then_deadline_then_number(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed).json()

    assert [item["priority"]["level"] for item in payload["items"]] == [1, 1, 2, 2, 3]
    first, second = payload["items"][0], payload["items"][1]
    assert first["sla"]["remaining_seconds"] < 0
    assert first["sla"]["state"] == "overdue"
    assert 0 < second["sla"]["remaining_seconds"] <= 20 * 60
    assert payload["items"][2]["sla"]["remaining_seconds"] <= 10 * 60
    assert payload["items"][3]["sla"]["state"] == "no_sla"
    assert payload["items"][3]["sla"]["deadline"] is None


def test_category_null_is_serialized(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed).json()
    item = next(row for row in payload["items"] if row["number"] == "TK-000104")
    assert item["category"] is None


def test_pagination_without_overlaps(seeded_client) -> None:
    client, seed = seeded_client.client, seeded_client.seed

    page1 = get(client, seed, "?page=1&page_size=2").json()
    page2 = get(client, seed, "?page=2&page_size=2").json()
    page3 = get(client, seed, "?page=3&page_size=2").json()

    assert numbers(page1) == ["TK-000101", "TK-000102"]
    assert numbers(page2) == ["TK-000103", "TK-000104"]
    assert numbers(page3) == ["TK-000105"]

    seen = numbers(page1) + numbers(page2) + numbers(page3)
    assert len(seen) == len(set(seen)) == 5

    assert page1["pagination"]["total_pages"] == 3
    assert page1["pagination"]["has_next"] is True
    assert page1["pagination"]["has_previous"] is False
    assert page3["pagination"]["has_next"] is False
    assert page3["pagination"]["has_previous"] is True


def test_page_out_of_range_returns_last_page(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed, "?page=99&page_size=2").json()
    assert payload["pagination"]["page"] == 3
    assert numbers(payload) == ["TK-000105"]


def test_sla_parity_values_for_active_tickets(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed).json()
    short_sla = next(row for row in payload["items"] if row["number"] == "TK-000102")
    assert short_sla["sla"]["total_seconds"] == 30 * 60
    assert short_sla["sla"]["warning_threshold_seconds"] == 15 * 60
    assert short_sla["sla"]["state"] == "on_time"
    assert short_sla["sla"]["outcome"] is None
    assert short_sla["sla"]["finalized_at"] is None


# ---------------------------------------------------------------------------
# T076 · Filtros, contadores y orden mixto
# ---------------------------------------------------------------------------


def test_filter_by_status(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed, "?status=en_progreso").json()
    assert numbers(payload) == ["TK-000101", "TK-000103"]
    assert payload["pagination"]["total_items"] == 2
    assert payload["applied_filters"]["status"] == ["en_progreso"]
    assert payload["applied_filters"]["is_default"] is False


def test_filter_by_priority_level(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed, "?priority=1").json()
    assert numbers(payload) == ["TK-000101", "TK-000102"]
    assert payload["applied_filters"]["priority"] == [1]


def test_combined_filters_use_and(seeded_client) -> None:
    payload = get(
        seeded_client.client,
        seeded_client.seed,
        "?status=en_progreso&priority=2",
    ).json()
    assert numbers(payload) == ["TK-000103"]
    assert payload["pagination"]["total_items"] == 1


def test_finalized_only_filter_and_historical_outcome(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed, "?status=resuelto").json()
    assert numbers(payload) == ["TK-000106"]
    item = payload["items"][0]
    assert item["is_final"] is True
    assert item["status_label"] == "Resuelto"
    assert item["sla"]["state"] == "finalized"
    assert item["sla"]["outcome"] == "met"
    assert item["sla"]["remaining_seconds"] is None
    assert item["sla"]["warning_threshold_seconds"] is None

    closed = get(seeded_client.client, seeded_client.seed, "?status=cerrado").json()
    assert numbers(closed) == ["TK-000107"]
    assert closed["items"][0]["sla"]["outcome"] == "breached"
    assert closed["items"][0]["sla"]["breach_delay_seconds"] > 0


def test_finalized_are_last_and_ordered_by_finalized_at_desc(seeded_client) -> None:
    all_statuses = "abierto,en_progreso,pendiente_usuario,resuelto,cerrado"
    payload = get(
        seeded_client.client, seeded_client.seed, f"?status={all_statuses}"
    ).json()

    assert numbers(payload) == A_ACTIVE_ORDER + ["TK-000107", "TK-000106"]
    assert [item["is_final"] for item in payload["items"]] == [
        False,
        False,
        False,
        False,
        False,
        True,
        True,
    ]


def test_counts_ignore_filters(seeded_client) -> None:
    payload = get(
        seeded_client.client, seeded_client.seed, "?status=resuelto&priority=4"
    ).json()
    assert payload["pagination"]["total_items"] == 0
    assert payload["counts"] == {"active": 5, "finalized": 2}


def test_available_filters_without_per_option_counters(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed).json()
    filters = payload["available_filters"]

    assert [option["value"] for option in filters["statuses"]] == [
        "abierto",
        "en_progreso",
        "pendiente_usuario",
        "resuelto",
        "cerrado",
    ]
    assert filters["statuses"][3] == {
        "value": "resuelto",
        "label": "Resuelto",
        "is_final": True,
    }
    assert [option["level"] for option in filters["priorities"]] == [1, 2, 3]
    assert filters["default_statuses"] == [
        "abierto",
        "en_progreso",
        "pendiente_usuario",
    ]
    for option in filters["statuses"] + filters["priorities"]:
        assert "count" not in option


def test_empty_page_shape_when_no_match(seeded_client) -> None:
    payload = get(seeded_client.client, seeded_client.seed, "?priority=4").json()
    assert payload["items"] == []
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 25,
        "total_items": 0,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }


# ---------------------------------------------------------------------------
# T077 · Autenticación, errores y cola vacía
# ---------------------------------------------------------------------------


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get(ENDPOINT)
    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "not_authenticated", "message": "La sesión no es válida o ha caducado."}
    }


def test_invalid_token_returns_401(seeded_client) -> None:
    response = seeded_client.client.get(
        ENDPOINT, headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


def test_token_signed_with_other_secret_returns_401(seeded_client) -> None:
    headers = seeded_client.seed.header_for("a", secret="otro-secreto")
    response = seeded_client.client.get(ENDPOINT, headers=headers)
    assert response.status_code == 401


def test_expired_token_returns_401(seeded_client) -> None:
    headers = seeded_client.seed.header_for("a", expires_delta=timedelta(seconds=-60))
    response = seeded_client.client.get(ENDPOINT, headers=headers)
    assert response.status_code == 401


def test_non_technician_role_returns_403(seeded_client) -> None:
    for key in ("supervisor", "usuario"):
        response = seeded_client.client.get(
            ENDPOINT, headers=seeded_client.seed.header_for(key)
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "forbidden"
        assert (
            response.json()["detail"]["message"]
            == "Esta vista está disponible solo para técnicos."
        )


def test_invalid_status_returns_422(seeded_client) -> None:
    response = get(seeded_client.client, seeded_client.seed, "?status=desconocido")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_query_parameter"
    assert "desconocido" in detail["message"]


def test_empty_status_returns_422(seeded_client) -> None:
    response = get(seeded_client.client, seeded_client.seed, "?status=")
    assert response.status_code == 422


def test_invalid_priority_returns_422(seeded_client) -> None:
    for value in ("5", "0", "alta", "1,,2"):
        response = get(seeded_client.client, seeded_client.seed, f"?priority={value}")
        assert response.status_code == 422, value


def test_invalid_pagination_returns_422(seeded_client) -> None:
    for value in ("page=0", "page_size=0", "page_size=101", "page=-1"):
        response = get(seeded_client.client, seeded_client.seed, f"?{value}")
        assert response.status_code == 422, value


def test_technician_without_tickets_gets_empty_queue(seeded_client) -> None:
    response = seeded_client.client.get(
        ENDPOINT, headers=seeded_client.seed.header_for("d")
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["total_pages"] == 0
    assert payload["counts"] == {"active": 0, "finalized": 0}
    assert payload["available_filters"]["priorities"] == []


def test_only_finalized_technician_gets_empty_default_items(seeded_client) -> None:
    response = seeded_client.client.get(
        ENDPOINT, headers=seeded_client.seed.header_for("c")
    )
    payload = response.json()
    assert payload["items"] == []
    assert payload["counts"] == {"active": 0, "finalized": 1}


def test_unexpected_error_returns_500(seeded_client, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr("app.api.v1.work_queue.build_work_queue", boom)
    response = get(seeded_client.client, seeded_client.seed)
    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "internal_error",
            "message": "No se pudo cargar la cola de trabajo.",
        }
    }


# ---------------------------------------------------------------------------
# T089 · Rendimiento con 100 tickets
# ---------------------------------------------------------------------------


def _add_extra_tickets(db: Session, seed: SeededQueue, count: int = 100) -> None:
    priority_cycle = [1, 2, 3, 4]
    for index in range(count):
        level = priority_cycle[index % len(priority_cycle)]
        created = seed.now - timedelta(hours=2)
        deadline = seed.now + timedelta(hours=1, minutes=index)
        db.add(
            Ticket(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu04-perf-{index}"),
                number=f"TK-9{index:05d}",
                title=f"Ticket de rendimiento {index}",
                status=TicketStatus.abierto,
                priority_id=seed.priorities[level].id,
                category_id=seed.categories["software"].id,
                creator_id=seed.users["a"].id,
                assignee_id=seed.users["a"].id,
                created_at=created,
                sla_deadline=deadline,
                sla_version="v1",
            )
        )
    db.commit()


def test_performance_with_100_tickets(seeded_client, db: Session) -> None:
    client, seed = seeded_client.client, seeded_client.seed
    _add_extra_tickets(db, seed)

    started = time.perf_counter()
    result = build_work_queue(
        db, seed.users["a"], WorkQueueQuery(page=1, page_size=100)
    )
    query_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    response = get(client, seed, "?page=1&page_size=100")
    endpoint_elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert result.pagination.total_items == 105
    assert len(response.json()["items"]) == 100
    assert query_elapsed < 0.300, f"consulta demasiado lenta: {query_elapsed:.3f}s"
    assert endpoint_elapsed < 2.0, f"endpoint demasiado lento: {endpoint_elapsed:.3f}s"

    expected_indexes = {
        "ix_tickets_assignee_status_deadline",
        "ix_tickets_assignee_finalized_at",
        "ix_tickets_assignee_priority",
        "ix_tickets_number",
    }
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

    if dialect == "sqlite":
        index_rows = db.execute(text("PRAGMA index_list('tickets')")).all()
        index_names = {row[1] for row in index_rows}
        assert expected_indexes <= index_names

        plan = db.execute(
            text(
                "EXPLAIN QUERY PLAN "
                "SELECT id FROM tickets "
                "WHERE assignee_id = :assignee "
                "AND status IN ('abierto','en_progreso','pendiente_usuario') "
                "ORDER BY sla_deadline LIMIT 25"
            ),
            {"assignee": seed.users["a"].id.hex},
        ).all()
        plan_text = " | ".join(str(row[-1]) for row in plan)
    else:
        index_rows = db.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'tickets'")
        ).scalars().all()
        assert expected_indexes <= set(index_rows)

        plan = db.execute(
            text(
                "EXPLAIN "
                "SELECT id FROM tickets "
                "WHERE assignee_id = :assignee "
                "AND status IN ('abierto','en_progreso','pendiente_usuario') "
                "ORDER BY sla_deadline LIMIT 25"
            ),
            {"assignee": seed.users["a"].id},
        ).all()
        plan_text = " | ".join(str(row[0]) for row in plan)

    print(f"Plan de consulta ({dialect}): {plan_text}")
    assert plan_text
