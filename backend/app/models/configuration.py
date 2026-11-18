"""Versiones, reglas SLA y auditoría de configuración (HU-08)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.category import Category
from app.models.enums import ConfigAction, ConfigEntityType
from app.models.priority import Priority
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConfigurationVersion(Base):
    __tablename__ = "configuration_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_configuration_versions_version_positive"),
        UniqueConstraint("version", name="uq_configuration_versions_version"),
        Index("ix_configuration_versions_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by: Mapped[User | None] = relationship(lazy="joined")


class SlaRule(Base):
    __tablename__ = "sla_rules"
    __table_args__ = (
        CheckConstraint("hours > 0", name="ck_sla_rules_hours_positive"),
        CheckConstraint(
            "valid_to_version IS NULL OR valid_to_version > valid_from_version",
            name="ck_sla_rules_valid_range",
        ),
        CheckConstraint(
            "retired_at IS NULL OR valid_to_version IS NOT NULL",
            name="ck_sla_rules_retired_range",
        ),
        UniqueConstraint(
            "category_id",
            "priority_id",
            "valid_from_version",
            name="uq_sla_rules_version_combination",
        ),
        Index(
            "uq_sla_rules_current_combination",
            "category_id",
            "priority_id",
            unique=True,
            postgresql_where=text("valid_to_version IS NULL"),
            sqlite_where=text("valid_to_version IS NULL"),
        ),
        Index("ix_sla_rules_category_priority", "category_id", "priority_id"),
        Index(
            "ix_sla_rules_current",
            "category_id",
            "priority_id",
            "valid_to_version",
        ),
        Index("ix_sla_rules_version", "configuration_version_id"),
        Index("ix_sla_rules_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("categories.id"), nullable=False
    )
    priority_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("priorities.id"), nullable=False
    )
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    configuration_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("configuration_versions.id"), nullable=False
    )
    valid_from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_to_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sla_rules.id"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )

    category: Mapped[Category] = relationship(lazy="joined")
    priority: Mapped[Priority] = relationship(lazy="joined")
    configuration_version: Mapped[ConfigurationVersion] = relationship(lazy="joined")
    created_by: Mapped[User] = relationship(
        lazy="joined", foreign_keys=[created_by_id]
    )


class ConfigurationAuditEntry(Base):
    __tablename__ = "configuration_audit_entries"
    __table_args__ = (
        Index("ix_config_audit_occurred_at", "occurred_at"),
        Index("ix_config_audit_entity", "entity_type", "entity_id"),
        Index("ix_config_audit_version", "configuration_version_id"),
        Index("ix_config_audit_actor", "actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    configuration_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("configuration_versions.id"), nullable=False
    )
    entity_type: Mapped[ConfigEntityType] = mapped_column(
        Enum(
            ConfigEntityType,
            name="config_entity_type",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[ConfigAction] = mapped_column(
        Enum(
            ConfigAction,
            name="config_action",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    previous_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)

    configuration_version: Mapped[ConfigurationVersion] = relationship(lazy="joined")
    actor: Mapped[User] = relationship(lazy="joined")
