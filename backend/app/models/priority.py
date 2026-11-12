"""Modelo de prioridad del ticket.

Convención del modelo base: `level = 1` es Crítica y `level = 4` es Baja.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Priority(Base):
    __tablename__ = "priorities"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 4", name="ck_priorities_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    base_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    keywords: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
