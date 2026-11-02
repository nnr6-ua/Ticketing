"""Modelos del dominio expuestos por el paquete `app.models`."""

from app.models.category import Category
from app.models.enums import (
    DEFAULT_ACTIVE_STATUSES,
    FINAL_STATUSES,
    STATUS_LABELS,
    SlaOutcome,
    SlaState,
    TicketStatus,
    UserRole,
)
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User

__all__ = [
    "Category",
    "DEFAULT_ACTIVE_STATUSES",
    "FINAL_STATUSES",
    "Priority",
    "STATUS_LABELS",
    "SlaOutcome",
    "SlaState",
    "Ticket",
    "TicketStatus",
    "User",
    "UserRole",
]
