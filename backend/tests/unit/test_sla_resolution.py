from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.errors import ApiError
from app.models import ConfigurationVersion, Priority, SlaRule
from app.services.sla_resolution import resolve_sla


def _context(
    *,
    rule_hours: Decimal | None,
    base_hours: Decimal | None,
    version: int = 4,
    priority_level: int = 2,
):
    category_id = uuid.uuid4()
    config_version = ConfigurationVersion(id=uuid.uuid4(), version=version)
    priority = Priority(
        id=uuid.uuid4(),
        name="Alta",
        level=priority_level,
        base_hours=base_hours,
        is_active=True,
    )
    rule = None
    if rule_hours is not None:
        rule = SlaRule(
            id=uuid.uuid4(),
            category_id=category_id,
            priority_id=priority.id,
            hours=rule_hours,
            configuration_version_id=config_version.id,
            valid_from_version=version,
            created_by_id=uuid.uuid4(),
        )
    return {
        "category_id": category_id,
        "priority": priority,
        "current_rule": rule,
        "config_version": config_version,
    }


def test_rule_takes_precedence_over_base() -> None:
    context = _context(rule_hours=Decimal("2.50"), base_hours=Decimal("8.00"))

    resolution = resolve_sla(**context)

    assert resolution.hours == Decimal("2.50")
    assert resolution.source == "rule"
    assert resolution.rule_id == context["current_rule"].id
    assert resolution.config_version_id == context["config_version"].id
    assert resolution.priority_level == 2


def test_base_is_used_when_rule_is_absent() -> None:
    context = _context(rule_hours=None, base_hours=Decimal("7.50"), version=2, priority_level=3)

    resolution = resolve_sla(**context)

    assert resolution.hours == Decimal("7.50")
    assert resolution.source == "priority_base"
    assert resolution.rule_id is None
    assert resolution.config_version_id == context["config_version"].id


def test_hours_are_quantized_to_minutes() -> None:
    context = _context(rule_hours=Decimal("1.234"), base_hours=None)

    resolution = resolve_sla(**context)

    assert resolution.hours == Decimal("1.23")


def test_missing_hours_fail_with_configuration_error() -> None:
    with pytest.raises(ApiError) as error:
        resolve_sla(**_context(rule_hours=None, base_hours=None))

    assert error.value.status_code == 500
    assert error.value.code == "configuration_not_configured"


def test_non_positive_hours_are_rejected() -> None:
    with pytest.raises(ApiError) as error:
        resolve_sla(**_context(rule_hours=Decimal("0"), base_hours=Decimal("8.00")))

    assert error.value.code == "configuration_not_configured"
