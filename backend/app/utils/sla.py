"""Cálculo canónico de SLA (funciones puras y testeables).

Todas las fechas se normalizan a UTC antes de operar; Europe/Madrid se usa
solo para presentar fechas en el cliente.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.models.enums import SlaOutcome, SlaState

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE


def as_utc(value: datetime) -> datetime:
    """Devuelve el instante en UTC, asumiendo UTC si no trae zona."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def warning_threshold_seconds(total_seconds: int) -> int:
    """Umbral de aviso: mitad si el SLA dura menos de 60 min; si no, 25 %."""

    if total_seconds < SECONDS_PER_HOUR:
        return total_seconds // 2
    return max(SECONDS_PER_HOUR, total_seconds // 4)


def classify_sla(
    *,
    is_final: bool,
    deadline: datetime | None,
    started_at: datetime | None,
    now: datetime,
) -> SlaState:
    """Clasifica el estado de SLA de un ticket."""

    if is_final:
        return SlaState.finalized
    if deadline is None or started_at is None:
        return SlaState.no_sla

    deadline_utc = as_utc(deadline)
    started_utc = as_utc(started_at)
    now_utc = as_utc(now)

    if deadline_utc <= started_utc:
        # Dato corrupto: no mostrar una alarma imposible.
        return SlaState.no_sla

    remaining = math.floor((deadline_utc - now_utc).total_seconds())
    total = math.floor((deadline_utc - started_utc).total_seconds())
    threshold = warning_threshold_seconds(total)

    if remaining < 0:
        return SlaState.overdue
    if remaining <= threshold:
        return SlaState.at_risk
    return SlaState.on_time


def sla_outcome(
    finalized_at: datetime | None, deadline: datetime | None
) -> SlaOutcome:
    """Resultado histórico de un ticket finalizado."""

    if deadline is None:
        return SlaOutcome.no_sla
    if finalized_at is None:
        return SlaOutcome.no_sla
    if as_utc(finalized_at) <= as_utc(deadline):
        return SlaOutcome.met
    return SlaOutcome.breached


def breach_delay_seconds(
    finalized_at: datetime | None, deadline: datetime | None
) -> int | None:
    """Segundos que se rebasó el límite al finalizar; `None` si no aplica."""

    if finalized_at is None or deadline is None:
        return None
    delay = math.floor((as_utc(finalized_at) - as_utc(deadline)).total_seconds())
    return delay if delay > 0 else None
