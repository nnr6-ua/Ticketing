from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Priority(Base):
    __tablename__ = "priorities"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="ck_priorities_name_length"),
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_priorities_level_range"),
        CheckConstraint(r"color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_priorities_color_format"),
        Index(
            "ux_priorities_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default AND is_active AND NOT is_system"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    color: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default="#64748b"
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(80)), nullable=False, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
