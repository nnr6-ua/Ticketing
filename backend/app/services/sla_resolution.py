"""Resolución pura del plazo aplicable a una combinación (HU-08)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import ApiError


@dataclass(frozen=True)
class SlaResolution:
    hours: Decimal
    source: str
    version: int
    priority_level: int


def resolve_sla(
    *,
    rule_hours: Decimal | None,
    base_hours: Decimal | None,
    version: int,
    priority_level: int,
) -> SlaResolution:
    hours = rule_hours if rule_hours is not None else base_hours
    if hours is None or hours <= 0:
        raise ApiError(
            500,
            "configuration_not_configured",
            "No hay un plazo SLA válido para la combinación seleccionada.",
        )
    return SlaResolution(
        hours=Decimal(hours).quantize(Decimal("0.01")),
        source="rule" if rule_hours is not None else "base",
        version=version,
        priority_level=priority_level,
    )
