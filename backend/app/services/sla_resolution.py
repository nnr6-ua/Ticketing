"""Resolución pura del plazo aplicable a una combinación (HU-08)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.core.errors import ApiError
from app.models import ConfigurationVersion, Priority, SlaRule


@dataclass(frozen=True)
class ResolvedSla:
    hours: Decimal
    priority_level: int
    source: Literal["rule", "priority_base"]
    rule_id: UUID | None
    config_version_id: UUID


def resolve_sla(
    *,
    category_id: UUID,
    priority: Priority,
    current_rule: SlaRule | None,
    config_version: ConfigurationVersion,
) -> ResolvedSla:
    if current_rule is not None and current_rule.category_id != category_id:
        raise ApiError(
            500,
            "configuration_not_configured",
            "La regla SLA no corresponde a la categoría seleccionada.",
        )
    hours = current_rule.hours if current_rule is not None else priority.base_hours
    if hours is None or hours <= 0:
        raise ApiError(
            500,
            "configuration_not_configured",
            "No hay un plazo SLA válido para la combinación seleccionada.",
        )
    return ResolvedSla(
        hours=Decimal(hours).quantize(Decimal("0.01")),
        priority_level=priority.level,
        source="rule" if current_rule is not None else "priority_base",
        rule_id=current_rule.id if current_rule is not None else None,
        config_version_id=config_version.id,
    )
