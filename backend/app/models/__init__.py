"""Modelos del dominio expuestos por el paquete `app.models`."""

from app.models.attachment import Attachment
from app.models.category import Category
from app.models.enums import (
    DEFAULT_ACTIVE_STATUSES,
    FINAL_STATUSES,
    STATUS_LABELS,
    SlaOutcome,
    SlaState,
    TicketStatus,
    TimelineEventType,
    UserRole,
)
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.timeline import TicketTimelineEntry
from app.models.user import User

__all__ = [
    "Attachment",
    "Category",
    "DEFAULT_ACTIVE_STATUSES",
    "FINAL_STATUSES",
    "Priority",
    "STATUS_LABELS",
    "SlaOutcome",
    "SlaState",
    "Ticket",
    "TicketStatus",
    "TicketTimelineEntry",
    "TimelineEventType",
    "User",
    "UserRole",
]
