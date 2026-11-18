"""Coherencia del semáforo en la API del dashboard (US4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import Ticket, TicketStatus
from app.utils.sla import SLA_AMBER_THRESHOLD_PCT, SLA_GREEN_THRESHOLD_PCT
from tests.integration._hu07 import API, get_dashboard

MADRID = ZoneInfo("Europe/Madrid")


def _day_at(day: date, hour: int = 10) -> datetime:
    return datetime.combine(day, time(hour=hour), tzinfo=MADRID)


def _add_resolved_batch(
    db,
    seed,
    *,
    day: date,
    on_time: int,
    late: int,
    key: str,
) -> None:
    """Crea tickets resueltos en un día natural propio del lote."""

    created = _day_at(day).astimezone(timezone.utc)
    deadline = created + timedelta(hours=4)

    tickets: list[Ticket] = []
    index = 0
    for within in (True, False):
        count = on_time if within else late
        for _ in range(count):
            finalized = (
                deadline - timedelta(minutes=30)
                if within
                else deadline + timedelta(minutes=30)
            )
            tickets.append(
                Ticket(
                    id=uuid.uuid5(
                        uuid.NAMESPACE_DNS, f"hu07-semaphore-{key}-{index}"
                    ),
                    number=f"TK-9{key.upper()}{index:04d}",
                    title="Ticket de semáforo",
                    description=None,
                    status=TicketStatus.resuelto,
                    priority_id=seed.priorities[3].id,
                    category_id=seed.categories["red"].id,
                    creator_id=seed.users["usuario"].id,
                    assignee_id=seed.users["tecnico_a"].id,
                    created_at=created,
                    sla_deadline=deadline,
                    finalized_at=finalized,
                    closed_at=finalized,
                    updated_at=created,
                    sla_version="v1",
                )
            )
            index += 1

    db.add_all(tickets)
    db.commit()


def _period(day: date) -> dict[str, str]:
    return {"desde": day.isoformat(), "hasta": day.isoformat()}


def _assert_semaphore_matches(compliance_pct: float | None, semaphore: str) -> None:
    if compliance_pct is None:
        assert semaphore == "sin_datos"
    elif compliance_pct >= SLA_GREEN_THRESHOLD_PCT:
        assert semaphore == "verde"
    elif compliance_pct >= SLA_AMBER_THRESHOLD_PCT:
        assert semaphore == "ambar"
    else:
        assert semaphore == "rojo"


def test_semaphore_is_consistent_across_every_section(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    data = body["data"]

    metrics = [data["summary"]]
    metrics.extend(data["matrix"])
    metrics.extend(data["priority_totals"])
    metrics.extend(data["category_totals"])

    for entry in metrics:
        pct = entry["compliance_pct"]
        assert pct is None or 0.0 <= pct <= 100.0
        _assert_semaphore_matches(pct, entry["semaphore"])


def test_meta_thresholds_are_exact(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)

    assert body["meta"]["thresholds"] == {
        "green_pct": 90.0,
        "amber_pct": 70.0,
    }
    assert SLA_GREEN_THRESHOLD_PCT == 90.0
    assert SLA_AMBER_THRESHOLD_PCT == 70.0


def test_exactly_ninety_percent_is_green(client, db, dashboard_seed):
    day = (
        dashboard_seed.now.astimezone(MADRID) - timedelta(days=20)
    ).date()
    _add_resolved_batch(
        db,
        dashboard_seed,
        day=day,
        on_time=9,
        late=1,
        key="verde",
    )

    body = get_dashboard(
        client, dashboard_seed.supervisor_headers, **_period(day)
    )

    assert body["data"]["summary"]["compliance_pct"] == 90.0
    assert body["data"]["summary"]["semaphore"] == "verde"


def test_exactly_seventy_percent_is_amber(client, db, dashboard_seed):
    day = (
        dashboard_seed.now.astimezone(MADRID) - timedelta(days=21)
    ).date()
    _add_resolved_batch(
        db,
        dashboard_seed,
        day=day,
        on_time=7,
        late=3,
        key="ambar",
    )

    body = get_dashboard(
        client, dashboard_seed.supervisor_headers, **_period(day)
    )

    assert body["data"]["summary"]["compliance_pct"] == 70.0
    assert body["data"]["summary"]["semaphore"] == "ambar"


def test_below_seventy_percent_is_red(client, dashboard_seed):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    summary = body["data"]["summary"]

    assert summary["compliance_pct"] < 70.0
    assert summary["semaphore"] == "rojo"


@pytest.mark.parametrize("path", [API])
def test_no_metric_has_out_of_range_percentage(client, dashboard_seed, path):
    body = get_dashboard(client, dashboard_seed.supervisor_headers)
    data = body["data"]

    for entry in [
        data["summary"],
        *data["matrix"],
        *data["priority_totals"],
        *data["category_totals"],
    ]:
        pct = entry["compliance_pct"]
        if pct is not None:
            assert 0.0 <= pct <= 100.0
