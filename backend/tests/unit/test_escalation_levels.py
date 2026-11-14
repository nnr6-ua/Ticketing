"""Pruebas unitarias del catálogo de niveles de escalado (HU-06, T004)."""

from __future__ import annotations

import pytest

from app.models import (
    ESCALATION_LEVEL_LABELS,
    ESCALATION_LEVEL_ORDER,
    EscalationLevel,
)
from app.services.assignee_change import (
    escalation_level_label,
    higher_escalation_levels,
    is_higher_level,
)


def test_level_order_is_total_and_ascending() -> None:
    assert ESCALATION_LEVEL_ORDER == (
        EscalationLevel.nivel_1,
        EscalationLevel.nivel_2,
        EscalationLevel.especialista,
    )
    assert len(set(ESCALATION_LEVEL_ORDER)) == 3


def test_labels_are_spanish_catalog_labels() -> None:
    assert escalation_level_label(EscalationLevel.nivel_1) == "Nivel 1"
    assert escalation_level_label(EscalationLevel.nivel_2) == "Nivel 2"
    assert escalation_level_label(EscalationLevel.especialista) == "Especialista"
    assert ESCALATION_LEVEL_LABELS[EscalationLevel.nivel_2] == "Nivel 2"
    assert set(ESCALATION_LEVEL_LABELS) == set(ESCALATION_LEVEL_ORDER)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (
            EscalationLevel.nivel_1,
            (EscalationLevel.nivel_2, EscalationLevel.especialista),
        ),
        (EscalationLevel.nivel_2, (EscalationLevel.especialista,)),
        (EscalationLevel.especialista, ()),
    ],
)
def test_higher_escalation_levels(current, expected) -> None:
    assert higher_escalation_levels(current) == expected


def test_specialist_has_no_higher_levels() -> None:
    assert higher_escalation_levels(EscalationLevel.especialista) == ()


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (EscalationLevel.nivel_1, EscalationLevel.nivel_2, True),
        (EscalationLevel.nivel_1, EscalationLevel.especialista, True),
        (EscalationLevel.nivel_2, EscalationLevel.especialista, True),
        (EscalationLevel.nivel_1, EscalationLevel.nivel_1, False),
        (EscalationLevel.nivel_2, EscalationLevel.nivel_1, False),
        (EscalationLevel.especialista, EscalationLevel.nivel_1, False),
        (EscalationLevel.especialista, EscalationLevel.especialista, False),
    ],
)
def test_is_higher_level_is_strict(current, target, expected) -> None:
    assert is_higher_level(current, target) is expected
