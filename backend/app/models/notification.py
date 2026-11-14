"""Modelo de notificación personal del cambio de responsable (HU-06)."""

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
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NotificationType
from app.models.ticket import utcnow
from app.models.user import User


class Notification(Base):
    """Notificación dirigida al nuevo responsable de un ticket."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(is_read = false AND read_at IS NULL) OR "
            "(is_read = true AND read_at IS NOT NULL)",
            name="ck_notifications_read_at",
        ),
        UniqueConstraint(
            "timeline_entry_id", name="uq_notifications_timeline_entry"
        ),
        Index(
            "ix_notifications_recipient_read_created",
            "recipient_id",
            "is_read",
            "created_at",
        ),
        Index("ix_notifications_ticket", "ticket_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    timeline_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ticket_timeline_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    ticket_number: Mapped[str] = mapped_column(String(20), nullable=False)
    ticket_title: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_assignee_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    recipient: Mapped[User] = relationship(lazy="joined", foreign_keys=[recipient_id])
