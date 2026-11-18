"""Pruebas de integración de filtros y opciones del dashboard (US3)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import Ticket, TicketStatus
from tests.integration._hu07 import API, OPTIONS_API, get_dashboard

MADRID = ZoneInfo("Europe/Madrid")
UTC = timezone.utc


def _add_control_ticket(
    db, seed, number: str, created: datetime, *, assignee_id=None
) -> Ticket:
    """Ticket de control creado exactamente en el instante indicado."""

    ticket = Ticket(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"hu07-filter-{number}"),
        number=number,
        title=f"Ticket de control {number}",
        description="Ticket de control para los límites del periodo.",
        status=TicketStatus.abierto,
        priority_id=seed.priorities[1].id,
        category_id=seed.categories["red"].id,
        creator_id=seed.users["usuario"].id,
        assignee_id=assignee_id,
        created_at=created,
        sla_deadline=created + timedelta(hours=4),
        finalized_at=None,
        closed_at=None,
        updated_at=created,
        sla_version="v1",
    )
    db.add(ticket)
    return ticket


def test_default_period_is_last_30_natural_days(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    filters = body["meta"]["filters"]

    today = dashboard_seed.now.astimezone(MADRID).date()
    assert filters["desde"] == (today - timedelta(days=29)).isoformat()
    assert filters["hasta"] == today.isoformat()
    assert filters["categorias"] == []
    assert filters["prioridades"] == []


def test_both_period_bounds_are_inclusive(db, client, dashboard_seed):
    target = dashboard_seed.now.astimezone(MADRID).date() - timedelta(days=40)
    previous_day = datetime.combine(
        target - timedelta(days=1), time(23, 59, 59), tzinfo=MADRID
    )
    first_instant = datetime.combine(target, time.min, tzinfo=MADRID)
    last_instant = datetime.combine(target, time(23, 59, 59), tzinfo=MADRID)
    next_day = datetime.combine(target + timedelta(days=1), time.min, tzinfo=MADRID)

    _add_control_ticket(db, dashboard_seed, "TK-000901", previous_day.astimezone(UTC))
    _add_control_ticket(db, dashboard_seed, "TK-000902", first_instant.astimezone(UTC))
    _add_control_ticket(db, dashboard_seed, "TK-000903", last_instant.astimezone(UTC))
    _add_control_ticket(db, dashboard_seed, "TK-000904", next_day.astimezone(UTC))
    db.commit()

    body = get_dashboard(
        client,
        dashboard_seed.supervisor_headers,
        desde=target.isoformat(),
        hasta=target.isoformat(),
    )
    data = body["data"]

    # Solo el primer y el último instante del día natural están dentro.
    assert body["meta"]["has_tickets"] is True
    assert body["meta"]["filters"]["desde"] == target.isoformat()
    assert body["meta"]["filters"]["hasta"] == target.isoformat()
    assert data["summary"]["ticket_count"] == 2
    assert sum(row["ticket_count"] for row in data["matrix"]) == 2


def test_category_filter_uses_or_and_sin_categoria(client, dashboard_seed):
    headers = dashboard_seed.supervisor_headers

    red_id = str(dashboard_seed.categories["red"].id)
    solo_red = get_dashboard(client, headers, categorias=red_id)
    assert solo_red["data"]["summary"]["ticket_count"] == 3

    sin_categoria = get_dashboard(client, headers, categorias="sin_categoria")
    assert sin_categoria["data"]["summary"]["ticket_count"] == 2
    assert all(
        row["category_id"] is None for row in sin_categoria["data"]["matrix"]
    )

    combined = get_dashboard(
        client, headers, categorias=f"{red_id},sin_categoria"
    )
    assert combined["data"]["summary"]["ticket_count"] == 5


def test_priority_filter_uses_or_between_levels(client, dashboard_seed):
    headers = dashboard_seed.supervisor_headers

    level_one = get_dashboard(client, headers, prioridades="1")
    assert level_one["data"]["summary"]["ticket_count"] == 2

    levels = get_dashboard(client, headers, prioridades="1,2")
    assert levels["data"]["summary"]["ticket_count"] == 4
    assert {row["priority_level"] for row in levels["data"]["matrix"]} == {1, 2}


def test_dimensions_combine_with_and_and_share_population(client, dashboard_seed):
    headers = dashboard_seed.supervisor_headers
    red_id = str(dashboard_seed.categories["red"].id)

    body = get_dashboard(client, headers, categorias=red_id, prioridades="1")
    data = body["data"]

    assert data["summary"]["ticket_count"] == 2
    assert sum(row["ticket_count"] for row in data["matrix"]) == 2
    assert sum(row["ticket_count"] for row in data["priority_totals"]) == 2
    assert sum(row["ticket_count"] for row in data["category_totals"]) == 2
    assert sum(row["overdue_count"] for row in data["matrix"]) == (
        data["summary"]["overdue_count"]
    )


def test_invalid_date_range_is_422_with_stable_code(client, dashboard_seed):
    response = client.get(
        API,
        headers=dashboard_seed.supervisor_headers,
        params={"desde": "2026-11-10", "hasta": "2026-11-01"},
    )

    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_date_range"
    assert detail["message"] == (
        "La fecha inicial no puede ser posterior a la fecha final."
    )
    assert "data" not in response.json()


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2026-13-01"},
        {"hasta": "no-es-fecha"},
        {"categorias": "no-es-un-uuid"},
        {"prioridades": "5"},
        {"prioridades": "0"},
        {"prioridades": "1,,2"},
    ],
)
def test_malformed_filters_are_422_invalid_request(client, dashboard_seed, params):
    response = client.get(API, headers=dashboard_seed.supervisor_headers, params=params)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert response.json()["detail"]["message"] == (
        "Revisa los filtros e inténtalo de nuevo."
    )


def test_options_reflect_period_and_include_inactive(client, dashboard_seed):
    response = client.get(
        OPTIONS_API, headers=dashboard_seed.supervisor_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()

    names = [option["name"] for option in body["categories"]]
    assert names == ["Hardware", "Red", "Software", "Sin categoría"]
    assert body["categories"][-1]["id"] is None

    software = next(
        option for option in body["categories"] if option["name"] == "Software"
    )
    assert software["is_active"] is False

    assert [option["level"] for option in body["priorities"]] == [1, 2, 3, 4]
    baja = next(option for option in body["priorities"] if option["level"] == 4)
    assert baja["is_active"] is False


def test_options_for_empty_period_are_empty(client, dashboard_seed):
    body = client.get(
        OPTIONS_API,
        headers=dashboard_seed.supervisor_headers,
        params={"desde": "2020-01-01", "hasta": "2020-01-31"},
    ).json()

    assert body["categories"] == []
    assert body["priorities"] == []


def test_dst_boundary_keeps_both_sides_without_duplicates(db, client, dashboard_seed):
    # El 2026-03-29 a las 02:00 Europe/Madrid los relojes pasan a las 03:00.
    # Los instantes se fijan en UTC para no depender de horas locales inexistentes.
    before_jump = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)  # 01:30 CET (antes)
    after_jump = datetime(2026, 3, 29, 1, 30, tzinfo=UTC)  # 03:30 CEST (después)
    last_day = datetime(2026, 3, 30, 21, 30, tzinfo=UTC)  # 23:30 CEST del día final
    outside = datetime(2026, 3, 28, 22, 30, tzinfo=UTC)  # 23:30 CET del día previo

    _add_control_ticket(db, dashboard_seed, "TK-000911", outside)
    _add_control_ticket(db, dashboard_seed, "TK-000912", before_jump)
    _add_control_ticket(db, dashboard_seed, "TK-000913", after_jump)
    _add_control_ticket(db, dashboard_seed, "TK-000914", last_day)
    db.commit()

    body = get_dashboard(
        client,
        dashboard_seed.supervisor_headers,
        desde="2026-03-29",
        hasta="2026-03-30",
    )
    data = body["data"]

    assert body["meta"]["filters"]["desde"] == "2026-03-29"
    assert body["meta"]["filters"]["hasta"] == "2026-03-30"
    assert data["summary"]["ticket_count"] == 3
    # Ninguno se duplica: la matriz reconcilia con el total de la población.
    assert sum(row["ticket_count"] for row in data["matrix"]) == 3
    assert sum(row["ticket_count"] for row in data["priority_totals"]) == 3


def test_filter_without_results_does_not_invent_rows(client, dashboard_seed):
    unknown = "00000000-0000-0000-0000-000000000123"
    body = get_dashboard(
        client, dashboard_seed.supervisor_headers, categorias=unknown
    )
    data = body["data"]

    assert body["meta"]["has_tickets"] is False
    assert data["summary"]["ticket_count"] == 0
    assert data["summary"]["compliance_pct"] is None
    assert data["summary"]["semaphore"] == "sin_datos"
    assert data["matrix"] == []
    assert data["priority_totals"] == []
    assert data["category_totals"] == []
    assert data["ranking"] == {
        "technicians": [],
        "unassigned": None,
        "overdue_total": 0,
    }
