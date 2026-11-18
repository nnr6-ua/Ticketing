from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import ApiError
from app.services.sla_resolution import resolve_sla


def test_rule_takes_precedence_over_base() -> None:
    resolution = resolve_sla(
        rule_hours=Decimal("2.50"),
        base_hours=Decimal("8.00"),
        version=4,
        priority_level=2,
    )

    assert resolution.hours == Decimal("2.50")
    assert resolution.source == "rule"
    assert resolution.version == 4
    assert resolution.priority_level == 2


def test_base_is_used_when_rule_is_absent() -> None:
    resolution = resolve_sla(
        rule_hours=None,
        base_hours=Decimal("7.5"),
        version=2,
        priority_level=3,
    )

    assert resolution.hours == Decimal("7.50")
    assert resolution.source == "base"


def test_hours_are_quantized_to_minutes() -> None:
    resolution = resolve_sla(
        rule_hours=Decimal("1.234"),
        base_hours=None,
        version=1,
        priority_level=1,
    )

    assert resolution.hours == Decimal("1.23")


def test_missing_hours_fail_with_configuration_error() -> None:
    with pytest.raises(ApiError) as error:
        resolve_sla(
            rule_hours=None,
            base_hours=None,
            version=1,
            priority_level=1,
        )

    assert error.value.status_code == 500
    assert error.value.code == "configuration_not_configured"


def test_non_positive_hours_are_rejected() -> None:
    with pytest.raises(ApiError) as error:
        resolve_sla(
            rule_hours=Decimal("0"),
            base_hours=Decimal("8.00"),
            version=1,
            priority_level=1,
        )

    assert error.value.code == "configuration_not_configured"
