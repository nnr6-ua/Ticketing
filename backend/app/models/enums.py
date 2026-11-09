"""Enumeraciones compartidas por modelos, esquemas y servicios."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    usuario = "usuario"
    tecnico = "tecnico"
    supervisor = "supervisor"
    admin = "admin"


class TicketStatus(str, Enum):
    abierto = "abierto"
    en_progreso = "en_progreso"
    pendiente_usuario = "pendiente_usuario"
    resuelto = "resuelto"
    cerrado = "cerrado"

    @property
    def is_final(self) -> bool:
        return self in (TicketStatus.resuelto, TicketStatus.cerrado)

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]


class TimelineEventType(str, Enum):
    status_change = "status_change"
    resolution = "resolution"
    internal_comment = "internal_comment"


class SlaState(str, Enum):
    on_time = "on_time"
    at_risk = "at_risk"
    overdue = "overdue"
    no_sla = "no_sla"
    finalized = "finalized"


class SlaOutcome(str, Enum):
    met = "met"
    breached = "breached"
    no_sla = "no_sla"


STATUS_LABELS: dict[TicketStatus, str] = {
    TicketStatus.abierto: "Abierto",
    TicketStatus.en_progreso: "En progreso",
    TicketStatus.pendiente_usuario: "Pendiente de usuario",
    TicketStatus.resuelto: "Resuelto",
    TicketStatus.cerrado: "Cerrado",
}

DEFAULT_ACTIVE_STATUSES: tuple[TicketStatus, ...] = (
    TicketStatus.abierto,
    TicketStatus.en_progreso,
    TicketStatus.pendiente_usuario,
)

FINAL_STATUSES: tuple[TicketStatus, ...] = (
    TicketStatus.resuelto,
    TicketStatus.cerrado,
)
