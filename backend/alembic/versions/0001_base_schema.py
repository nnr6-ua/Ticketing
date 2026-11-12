"""Esquema base de la mesa de ayuda.

Revision ID: 0001_base_schema
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_base_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Los tipos se crean explícitamente en `upgrade()`; `create_type=False` evita
# que `create_table` vuelva a emitir `CREATE TYPE` y falle con DuplicateObject.
user_role = postgresql.ENUM(
    "usuario",
    "tecnico",
    "supervisor",
    "admin",
    name="user_role",
    create_type=False,
)
ticket_status = postgresql.ENUM(
    "abierto",
    "en_progreso",
    "pendiente_usuario",
    "resuelto",
    "cerrado",
    name="ticket_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    ticket_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "priorities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("base_hours", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name="ck_priorities_level"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("priority_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "sla_deadline", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sla_version", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["priority_id"], ["priorities.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )

    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_assignee_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("priorities")
    op.drop_table("categories")
    op.drop_table("users")

    bind = op.get_bind()
    ticket_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
