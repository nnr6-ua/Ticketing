"""Pruebas de integración del snapshot del dashboard de SLA (US1)."""

from __future__ import annotations

from datetime import timezone

import pytest

from app.models import Ticket, TicketTimelineEntry
from app.models.enums import TicketStatus
from tests.integration._hu07 import API, assert_vary_authorization, get_dashboard


@pytest.fixture()
def dashboard(client, dashboard_seed):
    return client, dashboard_seed


def _find(rows, **criteria):
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise AssertionError(f"No se encontró la fila {criteria}: {rows}")


def test_snapshot_returns_all_sections_with_headers(dashboard):
    client, seed = dashboard
    response = client.get(API, headers=seed.supervisor_headers)

    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert_vary_authorization(response)

    body = response.json()
    assert set(body) == {"data", "meta"}
    assert set(body["data"]) == {
        "summary",
        "matrix",
        "priority_totals",
        "category_totals",
        "ranking",
    }
    assert body["meta"]["timezone"] == "Europe/Madrid"
    assert body["meta"]["has_tickets"] is True
    assert body["meta"]["generated_at"].endswith("Z")


def test_summary_metrics(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    summary = body["data"]["summary"]

    assert summary["ticket_count"] == 8
    assert summary["no_sla_count"] == 2
    assert summary["attended_with_sla"] == 3
    assert summary["on_time"] == 1
    assert summary["compliance_pct"] == 33.3
    assert summary["overdue_count"] == 4
    assert summary["semaphore"] == "rojo"
    assert summary["avg_response_seconds"] == pytest.approx(72000.0)


def test_matrix_only_contains_combinations_with_data(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    matrix = body["data"]["matrix"]

    assert len(matrix) == 7
    assert all(row["ticket_count"] > 0 for row in matrix)
    assert sum(row["ticket_count"] for row in matrix) == 8
    assert sum(row["overdue_count"] for row in matrix) == 4


def test_matrix_priority_and_category_order(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    matrix = body["data"]["matrix"]

    levels = [row["priority_level"] for row in matrix]
    assert levels == sorted(levels)

    for level in set(levels):
        category_names = [
            row["category_name"] for row in matrix if row["priority_level"] == level
        ]
        assert category_names == sorted(
            category_names,
            key=lambda name: (name == "Sin categoría", name.casefold()),
        )

    names = [row["category_name"] for row in matrix]
    assert "Sin categoría" in names


def test_totals_are_recalculated_from_tickets(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    data = body["data"]

    assert [row["priority_level"] for row in data["priority_totals"]] == [1, 2, 3, 4]
    assert sum(row["ticket_count"] for row in data["priority_totals"]) == 8
    assert sum(row["overdue_count"] for row in data["priority_totals"]) == 4

    for key in ("ticket_count", "no_sla_count", "attended_with_sla", "on_time", "overdue_count"):
        assert sum(row[key] for row in data["priority_totals"]) == data["summary"][key]
        assert sum(row[key] for row in data["category_totals"]) == data["summary"][key]

    category_names = [row["category_name"] for row in data["category_totals"]]
    assert category_names[-1] == "Sin categoría"


def test_labels_for_inactive_priority_and_category(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    matrix = body["data"]["matrix"]

    reabierto = _find(
        matrix, priority_level=4, category_name="Red"
    )
    assert reabierto["priority_is_active"] is False
    assert reabierto["category_is_active"] is True

    software = _find(matrix, priority_level=3, category_name="Software")
    assert software["category_is_active"] is False

    sin_categoria = _find(matrix, priority_level=2, category_name="Sin categoría")
    assert sin_categoria["category_id"] is None
    assert sin_categoria["category_is_active"] is None


def test_ticket_at_exact_deadline_counts_on_time(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    red_level_one = _find(
        body["data"]["matrix"], priority_level=1, category_name="Red"
    )

    assert red_level_one["ticket_count"] == 2
    assert red_level_one["attended_with_sla"] == 1
    assert red_level_one["on_time"] == 1
    assert red_level_one["compliance_pct"] == 100.0
    assert red_level_one["semaphore"] == "verde"


def test_tickets_without_sla_are_excluded_from_percentage_and_average(dashboard):
    _, seed = dashboard
    body = get_dashboard(dashboard[0], seed.supervisor_headers)
    hardware_level_two = _find(
        body["data"]["matrix"], priority_level=2, category_name="Hardware"
    )

    assert hardware_level_two["ticket_count"] == 1
    assert hardware_level_two["no_sla_count"] == 0
    assert hardware_level_two["attended_with_sla"] == 1
    assert hardware_level_two["overdue_count"] == 1
    assert hardware_level_two["compliance_pct"] == 0.0

    hardware_level_four = _find(
        body["data"]["matrix"], priority_level=4, category_name="Hardware"
    )
    assert hardware_level_four["no_sla_count"] == 1
    assert hardware_level_four["attended_with_sla"] == 0
    assert hardware_level_four["compliance_pct"] is None
    assert hardware_level_four["semaphore"] == "sin_datos"
    assert hardware_level_four["overdue_count"] == 0


def test_reopened_ticket_is_counted_once_with_first_finalization(dashboard):
    client, seed = dashboard
    body = get_dashboard(client, seed.supervisor_headers)
    ticket = seed.tickets["baja_reabierta"]

    assert ticket.status == TicketStatus.abierto
    assert ticket.finalized_at is None

    row = _find(body["data"]["matrix"], priority_level=4, category_name="Red")
    assert row["ticket_count"] == 1
    assert row["attended_with_sla"] == 1
    assert row["on_time"] == 0
    assert row["overdue_count"] == 1

    assert body["data"]["summary"]["ticket_count"] == 8


def test_dashboard_is_read_only(db, client, dashboard_seed):
    from sqlalchemy import func, select

    before_entries = db.scalar(
        select(func.count()).select_from(TicketTimelineEntry)
    )
    before_tickets = db.scalar(select(func.count()).select_from(Ticket))
    before_updated = {
        ticket.id: _iso(ticket.updated_at)
        for ticket in db.scalars(select(Ticket)).all()
    }

    response = client.get(API, headers=dashboard_seed.supervisor_headers)
    assert response.status_code == 200

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(TicketTimelineEntry)) == before_entries
    assert db.scalar(select(func.count()).select_from(Ticket)) == before_tickets
    assert {
        ticket.id: _iso(ticket.updated_at)
        for ticket in db.scalars(select(Ticket)).all()
    } == before_updated


def _iso(value):
    normalized = (
        value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    )
    return normalized.isoformat()
