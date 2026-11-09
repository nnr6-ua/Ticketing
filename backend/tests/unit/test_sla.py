"""Pruebas unitarias del cálculo canónico de SLA."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import SlaOutcome, SlaState
from app.utils.sla import (
    breach_delay_seconds,
    classify_sla,
    sla_outcome,
    warning_threshold_seconds,
)

NOW = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)
MADRID = ZoneInfo("Europe/Madrid")


@pytest.mark.parametrize(
    ("total_seconds", "expected"),
    [
        (30 * 60, 15 * 60),
        (59 * 60, 29 * 60 + 30),
        (60 * 60, 60 * 60),
        (4 * 60 * 60, 60 * 60),
        (24 * 60 * 60, 6 * 60 * 60),
        (0, 0),
    ],
)
def test_warning_threshold_seconds(total_seconds: int, expected: int) -> None:
    assert warning_threshold_seconds(total_seconds) == expected


def test_exact_zero_is_at_risk() -> None:
    deadline = NOW
    started = NOW - timedelta(hours=4)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.at_risk
    )


def test_one_second_after_deadline_is_overdue() -> None:
    deadline = NOW - timedelta(seconds=1)
    started = deadline - timedelta(hours=4)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.overdue
    )


def test_short_sla_boundary_15_30_is_on_time() -> None:
    deadline = NOW + timedelta(minutes=15, seconds=30)
    started = deadline - timedelta(minutes=30)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.on_time
    )


def test_short_sla_exact_threshold_is_at_risk() -> None:
    deadline = NOW + timedelta(minutes=15)
    started = deadline - timedelta(minutes=30)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.at_risk
    )


def test_short_sla_twenty_minutes_remaining_is_on_time() -> None:
    deadline = NOW + timedelta(minutes=20)
    started = deadline - timedelta(minutes=30)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.on_time
    )


def test_long_sla_ten_minutes_remaining_is_at_risk() -> None:
    deadline = NOW + timedelta(minutes=10)
    started = deadline - timedelta(hours=4)
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=NOW
        )
        is SlaState.at_risk
    )


def test_no_sla_when_deadline_missing() -> None:
    assert (
        classify_sla(
            is_final=False,
            deadline=None,
            started_at=NOW - timedelta(hours=1),
            now=NOW,
        )
        is SlaState.no_sla
    )


def test_corrupt_deadline_before_start_is_no_sla() -> None:
    assert (
        classify_sla(
            is_final=False,
            deadline=NOW - timedelta(hours=1),
            started_at=NOW,
            now=NOW,
        )
        is SlaState.no_sla
    )


def test_finalized_state_has_priority_over_deadline() -> None:
    assert (
        classify_sla(
            is_final=True,
            deadline=NOW - timedelta(hours=10),
            started_at=NOW - timedelta(hours=20),
            now=NOW,
        )
        is SlaState.finalized
    )


def test_sla_outcome_met() -> None:
    assert sla_outcome(NOW, NOW + timedelta(hours=1)) is SlaOutcome.met


def test_sla_outcome_breached() -> None:
    assert sla_outcome(NOW, NOW - timedelta(seconds=1)) is SlaOutcome.breached


def test_sla_outcome_no_sla() -> None:
    assert sla_outcome(NOW, None) is SlaOutcome.no_sla
    assert sla_outcome(None, NOW) is SlaOutcome.no_sla


def test_breach_delay_seconds() -> None:
    assert breach_delay_seconds(NOW, NOW - timedelta(hours=2)) == 2 * 60 * 60
    assert breach_delay_seconds(NOW, NOW + timedelta(hours=1)) is None
    assert breach_delay_seconds(None, NOW) is None
    assert breach_delay_seconds(NOW, None) is None


def test_dst_spring_forward_keeps_real_utc_seconds() -> None:
    """El salto de verano no añade ni quita una hora al SLA."""

    # 2026-03-29: a las 02:00 Europe/Madrid los relojes pasan a las 03:00.
    before = datetime(2026, 3, 29, 1, 30, tzinfo=MADRID)
    after = datetime(2026, 3, 29, 3, 30, tzinfo=MADRID)

    # En hora de pared hay 2 h, pero en UTC solo transcurre 1 h.
    assert (after - before) == timedelta(hours=2)
    assert (
        after.astimezone(timezone.utc) - before.astimezone(timezone.utc)
    ) == timedelta(hours=1)

    deadline = after.astimezone(timezone.utc)
    started = deadline - timedelta(hours=4)
    now = before.astimezone(timezone.utc)

    # Queda 1 h real de un SLA de 4 h: exactamente el umbral de aviso.
    # Si se restara hora local (2 h restantes) sería on_time.
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=now
        )
        is SlaState.at_risk
    )


def test_dst_fall_back_keeps_real_utc_seconds() -> None:
    """La repetición de las 02:00-02:59 no duplica ni recorta el SLA."""

    # 2026-10-25: a las 03:00 Europe/Madrid los relojes vuelven a las 02:00.
    before = datetime(2026, 10, 25, 1, 30, tzinfo=MADRID)
    after = datetime(2026, 10, 25, 3, 30, tzinfo=MADRID)

    # En hora de pared hay 2 h, pero en UTC transcurren 3 h.
    assert (after - before) == timedelta(hours=2)
    assert (
        after.astimezone(timezone.utc) - before.astimezone(timezone.utc)
    ) == timedelta(hours=3)

    deadline = after.astimezone(timezone.utc)
    started = deadline - timedelta(hours=12)
    now = before.astimezone(timezone.utc)

    # Quedan 3 h reales de un SLA de 12 h: exactamente el umbral de aviso.
    # Si se restara hora local (2 h restantes) sería on_time.
    assert (
        classify_sla(
            is_final=False, deadline=deadline, started_at=started, now=now
        )
        is SlaState.at_risk
    )
