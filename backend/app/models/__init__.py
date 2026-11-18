"""Modelos del dominio expuestos por el paquete `app.models`."""

from app.models.attachment import Attachment
from app.models.category import Category
from app.models.configuration import (
    ConfigurationAuditEntry,
    ConfigurationVersion,
    SlaRule,
)
from app.models.enums import (
    DEFAULT_ACTIVE_STATUSES,
    ESCALATION_LEVEL_LABELS,
    ESCALATION_LEVEL_ORDER,
    FINAL_STATUSES,
    STATUS_LABELS,
    AssigneeChangeKind,
    ConfigAction,
    ConfigEntityType,
    EscalationLevel,
    NotificationType,
    SlaOutcome,
    SlaState,
    TicketStatus,
    TimelineEventType,
    UserRole,
)
from app.models.notification import Notification
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.timeline import TicketTimelineEntry
from app.models.user import User

__all__ = [
    "AssigneeChangeKind",
    "Attachment",
    "Category",
    "ConfigAction",
    "ConfigEntityType",
    "ConfigurationAuditEntry",
    "ConfigurationVersion",
    "DEFAULT_ACTIVE_STATUSES",
    "ESCALATION_LEVEL_LABELS",
    "ESCALATION_LEVEL_ORDER",
    "EscalationLevel",
    "FINAL_STATUSES",
    "Notification",
    "NotificationType",
    "Priority",
    "SlaRule",
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
