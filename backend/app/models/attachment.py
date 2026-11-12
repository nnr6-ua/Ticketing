"""Modelo de adjunto de un ticket."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.ticket import Ticket, utcnow


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/gif')",
            name="ck_attachments_mime_type",
        ),
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 5242880",
            name="ck_attachments_size",
        ),
        Index("ix_attachments_ticket", "ticket_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    ticket: Mapped[Ticket] = relationship()
