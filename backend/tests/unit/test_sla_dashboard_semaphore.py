"""Pruebas de los umbrales y la banda del semáforo de HU-07."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.utils.sla import (
    SLA_AMBER_THRESHOLD_PCT,
    SLA_GREEN_THRESHOLD_PCT,
    compliance_band,
)


def test_thresholds_are_the_business_constants():
    assert SLA_GREEN_THRESHOLD_PCT == 90.0
    assert SLA_AMBER_THRESHOLD_PCT == 70.0


@pytest.mark.parametrize(
    ("pct", "expected"),
    [
        (100.0, "verde"),
        (90.0, "verde"),
        (90.1, "verde"),
        (89.9, "ambar"),
        (70.0, "ambar"),
        (69.9, "rojo"),
        (0.0, "rojo"),
        (Decimal("90.0"), "verde"),
        (Decimal("70.0"), "ambar"),
        (Decimal("69.9"), "rojo"),
    ],
)
def test_compliance_band_uses_upper_band_at_exact_thresholds(pct, expected):
    assert compliance_band(pct) == expected


def test_compliance_band_without_data_is_neutral():
    assert compliance_band(None) == "sin_datos"
