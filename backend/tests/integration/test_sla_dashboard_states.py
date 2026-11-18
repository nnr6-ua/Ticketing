"""Pruebas de estados vacíos y de error del dashboard (US5)."""

from __future__ import annotations

from datetime import timedelta

from tests.integration._hu07 import API, get_dashboard


def _period(dashboard_seed, *, days_back: int, days_forward: int = 0) -> dict:
    from zoneinfo import ZoneInfo

    today = dashboard_seed.now.astimezone(ZoneInfo("Europe/Madrid")).date()
    return {
        "desde": (today - timedelta(days=days_back)).isoformat(),
        "hasta": (today + timedelta(days=days_forward)).isoformat(),
    }


def test_empty_period_has_no_metrics(client, dashboard_seed):
    body = get_dashboard(
        client,
        dashboard_seed.supervisor_headers,
        desde="2020-01-01",
        hasta="2020-01-31",
    )
    data = body["data"]

    assert body["meta"]["has_tickets"] is False
    assert data["summary"] == {
        "ticket_count": 0,
        "no_sla_count": 0,
        "attended_with_sla": 0,
        "on_time": 0,
        "compliance_pct": None,
        "avg_response_seconds": None,
        "overdue_count": 0,
        "semaphore": "sin_datos",
    }
    assert data["matrix"] == []


def test_period_with_only_tickets_without_sla(client, dashboard_seed):
    # El ticket TK-000704 (sin SLA) se creó hace 1 día: su día natural solo
    # contiene ese ticket de control.
    from zoneinfo import ZoneInfo

    target = (
        dashboard_seed.now.astimezone(ZoneInfo("Europe/Madrid"))
        - timedelta(days=1)
    ).date()
    body = get_dashboard(
        client,
        dashboard_seed.supervisor_headers,
        desde=target.isoformat(),
        hasta=target.isoformat(),
    )
    data = body["data"]

    assert data["summary"]["ticket_count"] == 1
    assert data["summary"]["no_sla_count"] == 1
    assert data["summary"]["compliance_pct"] is None
    assert data["summary"]["semaphore"] == "sin_datos"
    assert data["summary"]["overdue_count"] == 0


def test_period_without_overdue_has_empty_ranking(client, dashboard_seed):
    body = get_dashboard(
        client,
        dashboard_seed.supervisor_headers,
        **_period(dashboard_seed, days_back=1),
    )

    assert body["data"]["ranking"]["technicians"] == []
    assert body["data"]["ranking"]["unassigned"] is None
    assert body["data"]["ranking"]["overdue_total"] == 0


def test_invalid_range_returns_no_partial_data(client, dashboard_seed):
    response = client.get(
        API,
        headers=dashboard_seed.supervisor_headers,
        params={"desde": "2026-11-10", "hasta": "2026-11-01"},
    )

    assert response.status_code == 422
    assert list(response.json()) == ["detail"]


def test_session_and_role_errors_do_not_expose_data(client, dashboard_seed):
    unauthorized = client.get(API)
    assert unauthorized.status_code == 401
    assert "data" not in unauthorized.json()

    forbidden = client.get(API, headers=dashboard_seed.headers_for("tecnico_a"))
    assert forbidden.status_code == 403
    assert "data" not in forbidden.json()
