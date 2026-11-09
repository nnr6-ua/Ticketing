"""Pruebas de la matriz 5×5 y las funciones puras de la máquina de estados."""

from __future__ import annotations

from app.models.enums import STATUS_LABELS, TicketStatus
from app.services.ticket_state_machine import (
    ALLOWED_TRANSITIONS,
    allowed_status_options,
    allowed_transitions,
    is_final_status,
    is_transition_allowed,
    status_label,
)

ALL_STATES = list(TicketStatus)

EXPECTED_TRANSITIONS = {
    (TicketStatus.abierto, TicketStatus.en_progreso),
    (TicketStatus.en_progreso, TicketStatus.pendiente_usuario),
    (TicketStatus.en_progreso, TicketStatus.resuelto),
    (TicketStatus.pendiente_usuario, TicketStatus.en_progreso),
    (TicketStatus.resuelto, TicketStatus.en_progreso),
    (TicketStatus.resuelto, TicketStatus.cerrado),
}


def test_matrix_is_total_for_all_five_states() -> None:
    assert len(ALL_STATES) == 5
    assert set(ALLOWED_TRANSITIONS) == set(ALL_STATES)
    for current in ALL_STATES:
        assert isinstance(ALLOWED_TRANSITIONS[current], frozenset)
        assert all(isinstance(target, TicketStatus) for target in ALLOWED_TRANSITIONS[current])


def test_exactly_the_six_allowed_transitions() -> None:
    allowed = {
        (current, target)
        for current in ALL_STATES
        for target in ALL_STATES
        if is_transition_allowed(current, target)
    }
    assert allowed == EXPECTED_TRANSITIONS
    assert len(allowed) == 6


def test_closed_has_no_outgoing_transitions() -> None:
    assert allowed_transitions(TicketStatus.cerrado) == ()
    for target in ALL_STATES:
        assert is_transition_allowed(TicketStatus.cerrado, target) is False


def test_there_are_no_self_transitions() -> None:
    for current in ALL_STATES:
        assert is_transition_allowed(current, current) is False


def test_allowed_transitions_have_stable_order() -> None:
    assert allowed_transitions(TicketStatus.abierto) == (
        TicketStatus.en_progreso,
    )
    assert allowed_transitions(TicketStatus.en_progreso) == (
        TicketStatus.pendiente_usuario,
        TicketStatus.resuelto,
    )
    assert allowed_transitions(TicketStatus.resuelto) == (
        TicketStatus.en_progreso,
        TicketStatus.cerrado,
    )


def test_allowed_status_options_match_labels_and_order() -> None:
    options = allowed_status_options(TicketStatus.en_progreso)
    assert [(option.value, option.label) for option in options] == [
        (TicketStatus.pendiente_usuario, "Pendiente de usuario"),
        (TicketStatus.resuelto, "Resuelto"),
    ]
    assert allowed_status_options(TicketStatus.cerrado) == []


def test_labels_are_spanish() -> None:
    expected = {
        TicketStatus.abierto: "Abierto",
        TicketStatus.en_progreso: "En progreso",
        TicketStatus.pendiente_usuario: "Pendiente de usuario",
        TicketStatus.resuelto: "Resuelto",
        TicketStatus.cerrado: "Cerrado",
    }
    for status, label in expected.items():
        assert status_label(status) == label
        assert STATUS_LABELS[status] == label


def test_final_statuses_are_reused_from_base_model() -> None:
    assert is_final_status(TicketStatus.resuelto) is True
    assert is_final_status(TicketStatus.cerrado) is True
    for status in (
        TicketStatus.abierto,
        TicketStatus.en_progreso,
        TicketStatus.pendiente_usuario,
    ):
        assert is_final_status(status) is False
