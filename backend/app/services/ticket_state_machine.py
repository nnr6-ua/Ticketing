"""Máquina de estados pura del ticket (RN-02).

No importa SQLAlchemy ni FastAPI: solo el enum de estados, las etiquetas y el
DTO `StatusOption`. La matriz es total para los cinco estados y conserva un
orden estable para la interfaz.
"""

from __future__ import annotations

from app.models.enums import STATUS_LABELS, TicketStatus
from app.schemas.ticket_workflow import StatusOption

ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.abierto: frozenset({TicketStatus.en_progreso}),
    TicketStatus.en_progreso: frozenset(
        {TicketStatus.pendiente_usuario, TicketStatus.resuelto}
    ),
    TicketStatus.pendiente_usuario: frozenset({TicketStatus.en_progreso}),
    TicketStatus.resuelto: frozenset(
        {TicketStatus.en_progreso, TicketStatus.cerrado}
    ),
    TicketStatus.cerrado: frozenset(),
}

# Orden legible para la interfaz. Coincide con la matriz anterior.
_ORDERED_TRANSITIONS: dict[TicketStatus, tuple[TicketStatus, ...]] = {
    TicketStatus.abierto: (TicketStatus.en_progreso,),
    TicketStatus.en_progreso: (
        TicketStatus.pendiente_usuario,
        TicketStatus.resuelto,
    ),
    TicketStatus.pendiente_usuario: (TicketStatus.en_progreso,),
    TicketStatus.resuelto: (TicketStatus.en_progreso, TicketStatus.cerrado),
    TicketStatus.cerrado: (),
}


def allowed_transitions(current: TicketStatus) -> tuple[TicketStatus, ...]:
    """Destinos permitidos desde `current`, en orden estable."""

    return _ORDERED_TRANSITIONS[current]


def is_transition_allowed(current: TicketStatus, target: TicketStatus) -> bool:
    """Indica si `current -> target` pertenece a la matriz."""

    return target in ALLOWED_TRANSITIONS[current]


def is_final_status(status: TicketStatus) -> bool:
    """Reutiliza la noción de estado final del modelo base."""

    return status.is_final


def status_label(status: TicketStatus) -> str:
    """Etiqueta es-ES del estado."""

    return STATUS_LABELS[status]


def allowed_status_options(current: TicketStatus) -> list[StatusOption]:
    """Opciones de destino listas para el contrato HTTP."""

    return [
        StatusOption(value=target, label=status_label(target))
        for target in allowed_transitions(current)
    ]
