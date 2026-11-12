from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 5 AND 120", name="ck_tickets_title_length"),
        CheckConstraint(
            "char_length(description) BETWEEN 20 AND 5000",
            name="ck_tickets_description_length",
        ),
        CheckConstraint(
            "status IN ('Abierto', 'En progreso', 'Pendiente de usuario', 'Resuelto', 'Cerrado')",
            name="ck_tickets_status",
        ),
        UniqueConstraint("creator_id", "content_hash", name="uq_tickets_creator_content_hash"),
        Index("ix_tickets_creator_created", "creator_id", "created_at"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_status_created", "status", "created_at"),
        Index("ix_tickets_priority_created", "priority_id", "created_at"),
        Index("ix_tickets_category_created", "category_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    ticket_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="Abierto")
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employees.id"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False
    )
    priority_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("priorities.id"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    creator: Mapped["Employee"] = relationship("Employee", lazy="joined")
    category: Mapped["Category"] = relationship("Category", lazy="joined")
    priority: Mapped["Priority"] = relationship("Priority", lazy="joined")
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        "TicketEvent",
        back_populates="ticket",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
