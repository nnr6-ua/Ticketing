"""Modelo append-only de la línea temporal del ticket (HU-05/HU-06)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AssigneeChangeKind,
    EscalationLevel,
    TicketStatus,
    TimelineEventType,
)
from app.models.ticket import Ticket, utcnow
from app.models.user import User


class TicketTimelineEntry(Base):
    """Entrada inmutable de la línea temporal de un ticket."""

    __tablename__ = "ticket_timeline_entries"
    __table_args__ = (
        CheckConstraint(
            "(event_type <> 'status_change') OR "
            "(from_status IS NOT NULL AND to_status IS NOT NULL "
            "AND from_status <> to_status AND body IS NULL "
            "AND is_internal = false)",
            name="ck_timeline_status_change",
        ),
        CheckConstraint(
            "(event_type <> 'resolution') OR "
            "(to_status = 'resuelto' AND body IS NOT NULL "
            "AND is_internal = false)",
            name="ck_timeline_resolution",
        ),
        CheckConstraint(
            "(event_type <> 'internal_comment') OR "
            "(from_status IS NULL AND to_status IS NULL "
            "AND body IS NOT NULL AND is_internal = true)",
            name="ck_timeline_internal_comment",
        ),
        CheckConstraint(
            "(event_type <> 'assignee_change') OR ("
            "body IS NOT NULL "
            "AND is_internal = false "
            "AND from_status IS NULL "
            "AND to_status IS NULL "
            "AND previous_assignee_id IS NOT NULL "
            "AND new_assignee_id IS NOT NULL "
            "AND previous_assignee_id <> new_assignee_id "
            "AND change_kind IS NOT NULL "
            "AND from_escalation_level IS NOT NULL "
            "AND to_escalation_level IS NOT NULL "
            "AND ("
            "(change_kind = 'reassignment' "
            "AND from_escalation_level = to_escalation_level) "
            "OR (change_kind = 'escalation' "
            "AND from_escalation_level <> to_escalation_level)"
            "))",
            name="ck_timeline_assignee_change",
        ),
        CheckConstraint(
            "body IS NULL OR (length(body) >= 1 AND length(body) <= 5000)",
            name="ck_timeline_body_length",
        ),
        CheckConstraint("event_order IN (0, 1)", name="ck_timeline_event_order"),
        UniqueConstraint(
            "ticket_id",
            "request_id",
            "event_type",
            name="uq_timeline_request_event",
        ),
        Index("ix_timeline_ticket_created", "ticket_id", "created_at"),
        Index("ix_timeline_ticket_internal", "ticket_id", "is_internal"),
        Index("ix_timeline_author", "author_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(
            TimelineEventType,
            name="timeline_event_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    from_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    to_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    event_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    previous_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    new_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    change_kind: Mapped[AssigneeChangeKind | None] = mapped_column(
        Enum(
            AssigneeChangeKind,
            name="assignee_change_kind",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    from_escalation_level: Mapped[EscalationLevel | None] = mapped_column(
        Enum(
            EscalationLevel,
            name="escalation_level",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    to_escalation_level: Mapped[EscalationLevel | None] = mapped_column(
        Enum(
            EscalationLevel,
            name="escalation_level",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )

    author: Mapped[User] = relationship(lazy="joined", foreign_keys=[author_id])
    previous_assignee: Mapped[User | None] = relationship(
        lazy="joined", foreign_keys=[previous_assignee_id]
    )
    new_assignee: Mapped[User | None] = relationship(
        lazy="joined", foreign_keys=[new_assignee_id]
    )
    ticket: Mapped[Ticket] = relationship()
