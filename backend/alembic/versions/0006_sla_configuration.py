"""Configuración versionada de catálogos y plazos SLA (HU-08).

Revision ID: 0006_sla_configuration
Revises: 0005_ticket_information
Create Date: 2026-11-17
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_sla_configuration"
down_revision: Union[str, None] = "0005_ticket_information"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASELINE_ID = uuid.UUID("0f5a7f8e-4ef7-4e0d-9a1e-9f6e2e3d4c10")

# Los tipos se crean explícitamente en `upgrade()`; `create_type=False` evita
# que `create_table` vuelva a emitir `CREATE TYPE` y falle con DuplicateObject.
config_entity_type = postgresql.ENUM(
    "category",
    "priority",
    "sla_rule",
    name="config_entity_type",
    create_type=False,
)
config_action = postgresql.ENUM(
    "create",
    "update",
    "deactivate",
    "reactivate",
    "delete",
    "set_default",
    "rule_upsert",
    "rule_retire",
    name="config_action",
    create_type=False,
)


def _ensure_unique_data() -> None:
    bind = op.get_bind()
    checks = [
        (
            "SELECT lower(trim(name)) AS key, COUNT(*) AS total "
            "FROM categories GROUP BY lower(trim(name)) HAVING COUNT(*) > 1",
            "Hay categorías con nombres duplicados; unifícalos antes de migrar.",
        ),
        (
            "SELECT lower(trim(name)) AS key, COUNT(*) AS total "
            "FROM priorities GROUP BY lower(trim(name)) HAVING COUNT(*) > 1",
            "Hay prioridades con nombres duplicados; unifícalos antes de migrar.",
        ),
        (
            "SELECT level AS key, COUNT(*) AS total FROM priorities "
            "WHERE is_active AND NOT is_system GROUP BY level HAVING COUNT(*) > 1",
            "Hay prioridades activas con el mismo nivel; libera los niveles antes de migrar.",
        ),
        (
            "SELECT 1 AS key, COUNT(*) AS total FROM categories "
            "WHERE is_default AND is_active AND NOT is_system "
            "HAVING COUNT(*) > 1",
            "Hay más de una categoría predeterminada activa; deja solo una.",
        ),
        (
            "SELECT 1 AS key, COUNT(*) AS total FROM priorities "
            "WHERE is_default AND is_active AND NOT is_system "
            "HAVING COUNT(*) > 1",
            "Hay más de una prioridad predeterminada activa; deja solo una.",
        ),
    ]
    for statement, message in checks:
        if bind.execute(sa.text(statement)).first() is not None:
            raise RuntimeError(message)


def upgrade() -> None:
    _ensure_unique_data()
    bind = op.get_bind()
    config_entity_type.create(bind, checkfirst=True)
    config_action.create(bind, checkfirst=True)
    op.create_table(
        "configuration_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "version > 0", name="ck_configuration_versions_version_positive"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_configuration_versions_version"),
    )
    op.create_index(
        "ix_configuration_versions_created_at",
        "configuration_versions",
        ["created_at"],
    )

    op.create_table(
        "sla_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("priority_id", sa.Uuid(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from_version", sa.Integer(), nullable=False),
        sa.Column("valid_to_version", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("hours > 0", name="ck_sla_rules_hours_positive"),
        sa.CheckConstraint(
            "valid_to_version IS NULL OR valid_to_version > valid_from_version",
            name="ck_sla_rules_valid_range",
        ),
        sa.CheckConstraint(
            "retired_at IS NULL OR valid_to_version IS NOT NULL",
            name="ck_sla_rules_retired_range",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"], ["configuration_versions.id"]
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["priority_id"], ["priorities.id"]),
        sa.ForeignKeyConstraint(["retired_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["sla_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_id",
            "priority_id",
            "valid_from_version",
            name="uq_sla_rules_version_combination",
        ),
    )
    op.create_index(
        "uq_sla_rules_current_combination",
        "sla_rules",
        ["category_id", "priority_id"],
        unique=True,
        postgresql_where=sa.text("valid_to_version IS NULL"),
        sqlite_where=sa.text("valid_to_version IS NULL"),
    )
    op.create_index(
        "ix_sla_rules_category_priority",
        "sla_rules",
        ["category_id", "priority_id"],
    )
    op.create_index(
        "ix_sla_rules_current",
        "sla_rules",
        ["category_id", "priority_id", "valid_to_version"],
    )
    op.create_index(
        "ix_sla_rules_version", "sla_rules", ["configuration_version_id"]
    )
    op.create_index("ix_sla_rules_created_at", "sla_rules", ["created_at"])

    op.create_table(
        "configuration_audit_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", config_entity_type, nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", config_action, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("previous_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["configuration_version_id"], ["configuration_versions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_config_audit_occurred_at",
        "configuration_audit_entries",
        ["occurred_at"],
    )
    op.create_index(
        "ix_config_audit_entity",
        "configuration_audit_entries",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_config_audit_version",
        "configuration_audit_entries",
        ["configuration_version_id"],
    )
    op.create_index(
        "ix_config_audit_actor", "configuration_audit_entries", ["actor_id"]
    )

    op.add_column(
        "categories",
        sa.Column(
            "revision", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
    )
    op.add_column(
        "priorities",
        sa.Column(
            "revision", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
    )
    op.create_index(
        "uq_categories_name_normalized",
        "categories",
        [sa.text("lower(trim(name))")],
        unique=True,
    )
    op.create_index(
        "uq_priorities_name_normalized",
        "priorities",
        [sa.text("lower(trim(name))")],
        unique=True,
    )
    op.create_index(
        "uq_priorities_level_active_non_system",
        "priorities",
        ["level"],
        unique=True,
        postgresql_where=sa.text("is_active AND NOT is_system"),
        sqlite_where=sa.text("is_active = 1 AND is_system = 0"),
    )
    op.create_index(
        "uq_categories_default_active_non_system",
        "categories",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default AND is_active AND NOT is_system"),
        sqlite_where=sa.text("is_default = 1 AND is_active = 1 AND is_system = 0"),
    )
    op.create_index(
        "uq_priorities_default_active_non_system",
        "priorities",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default AND is_active AND NOT is_system"),
        sqlite_where=sa.text("is_default = 1 AND is_active = 1 AND is_system = 0"),
    )

    op.add_column(
        "tickets",
        sa.Column("sla_priority_level", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "sla_hours_applied",
            sa.Numeric(precision=6, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_config_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tickets_sla_config_version",
        "tickets",
        "configuration_versions",
        ["sla_config_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_tickets_sla_priority_level",
        "tickets",
        "sla_priority_level IS NULL OR sla_priority_level BETWEEN 1 AND 4",
    )
    op.create_check_constraint(
        "ck_tickets_sla_hours_positive",
        "tickets",
        "sla_hours_applied IS NULL OR sla_hours_applied > 0",
    )
    op.create_index(
        "ix_tickets_sla_config_version", "tickets", ["sla_config_version_id"]
    )

    versions = sa.table(
        "configuration_versions",
        sa.column("id", sa.Uuid()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("created_by_id", sa.Uuid()),
        sa.column("note", sa.String()),
    )
    op.bulk_insert(
        versions,
        [
            {
                "id": BASELINE_ID,
                "version": 1,
                "created_at": datetime.now(timezone.utc),
                "created_by_id": None,
                "note": "Línea base de configuración",
            }
        ],
    )

    # Los tickets anteriores son legado: conservan su plazo y nivel actual,
    # pero no se les asigna la versión nueva.
    op.execute(
        "UPDATE tickets SET sla_priority_level = "
        "(SELECT level FROM priorities WHERE priorities.id = tickets.priority_id) "
        "WHERE sla_priority_level IS NULL"
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE tickets SET sla_hours_applied = "
            "ROUND(EXTRACT(EPOCH FROM (sla_deadline - created_at)) / 3600.0, 2) "
            "WHERE sla_deadline IS NOT NULL "
            "AND sla_deadline > created_at "
            "AND sla_hours_applied IS NULL"
        )
    else:
        op.execute(
            "UPDATE tickets SET sla_hours_applied = "
            "ROUND((julianday(sla_deadline) - julianday(created_at)) * 24, 2) "
            "WHERE sla_deadline IS NOT NULL "
            "AND sla_deadline > created_at "
            "AND sla_hours_applied IS NULL"
        )


def downgrade() -> None:
    op.drop_index("ix_tickets_sla_config_version", table_name="tickets")
    op.drop_constraint("ck_tickets_sla_hours_positive", "tickets", type_="check")
    op.drop_constraint("ck_tickets_sla_priority_level", "tickets", type_="check")
    op.drop_constraint(
        "fk_tickets_sla_config_version", "tickets", type_="foreignkey"
    )
    op.drop_column("tickets", "sla_config_version_id")
    op.drop_column("tickets", "sla_hours_applied")
    op.drop_column("tickets", "sla_priority_level")

    op.drop_index("uq_priorities_name_normalized", table_name="priorities")
    op.drop_index("uq_categories_name_normalized", table_name="categories")
    op.drop_index(
        "uq_priorities_default_active_non_system", table_name="priorities"
    )
    op.drop_index(
        "uq_categories_default_active_non_system", table_name="categories"
    )
    op.drop_index(
        "uq_priorities_level_active_non_system", table_name="priorities"
    )
    op.drop_column("priorities", "revision")
    op.drop_column("categories", "revision")

    op.drop_table("configuration_audit_entries")
    op.drop_table("sla_rules")
    op.drop_index(
        "ix_configuration_versions_created_at",
        table_name="configuration_versions",
    )
    op.drop_table("configuration_versions")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        config_action.drop(bind, checkfirst=True)
        config_entity_type.drop(bind, checkfirst=True)
