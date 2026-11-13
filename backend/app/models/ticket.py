"""Modelo de ticket con la columna de soporte `finalized_at`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.priority import Priority


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "(status IN ('resuelto', 'cerrado') AND finalized_at IS NOT NULL) "
            "OR (status NOT IN ('resuelto', 'cerrado') AND finalized_at IS NULL)",
            name="ck_tickets_finalized_at",
        ),
        CheckConstraint(
            "finalized_at IS NULL OR finalized_at >= created_at",
            name="ck_tickets_finalized_after_created",
        ),
        CheckConstraint(
            "sla_deadline IS NULL OR sla_deadline > created_at",
            name="ck_tickets_sla_deadline_after_created",
        ),
        Index(
            "ix_tickets_assignee_status_deadline",
            "assignee_id",
            "status",
            "sla_deadline",
        ),
        Index("ix_tickets_assignee_finalized_at", "assignee_id", "finalized_at"),
        Index("ix_tickets_assignee_priority", "assignee_id", "priority_id"),
        Index("ix_tickets_number", "number"),
        UniqueConstraint(
            "creator_id",
            "content_hash",
            name="uq_tickets_creator_content_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    priority_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("priorities.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id"), nullable=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    sla_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    sla_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    priority: Mapped[Priority] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
