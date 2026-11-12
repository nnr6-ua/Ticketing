"""Crea la tabla append-only de la línea temporal y su enum.

Revision ID: 0003_ticket_timeline
Revises: 0002_work_queue
Create Date: 2026-11-02

La migración es puramente aditiva: no altera `tickets` ni ninguna otra tabla
existente. `downgrade()` elimina primero los índices, después la tabla y por
último el tipo.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_ticket_timeline"
down_revision: Union[str, None] = "0002_work_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Los tipos se crean explícitamente; `create_type=False` evita que
# `create_table` vuelva a emitir `CREATE TYPE`. `ticket_status` ya existe desde
# la migración 0001.
timeline_event_type = postgresql.ENUM(
    "status_change",
    "resolution",
    "internal_comment",
    name="timeline_event_type",
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
    timeline_event_type.create(bind, checkfirst=True)

    op.create_table(
        "ticket_timeline_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", timeline_event_type, nullable=False),
        sa.Column("from_status", ticket_status, nullable=True),
        sa.Column("to_status", ticket_status, nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "event_order",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(event_type <> 'status_change') OR "
            "(from_status IS NOT NULL AND to_status IS NOT NULL "
            "AND from_status <> to_status AND body IS NULL "
            "AND is_internal = false)",
            name="ck_timeline_status_change",
        ),
        sa.CheckConstraint(
            "(event_type <> 'resolution') OR "
            "(to_status = 'resuelto' AND body IS NOT NULL "
            "AND is_internal = false)",
            name="ck_timeline_resolution",
        ),
        sa.CheckConstraint(
            "(event_type <> 'internal_comment') OR "
            "(from_status IS NULL AND to_status IS NULL "
            "AND body IS NOT NULL AND is_internal = true)",
            name="ck_timeline_internal_comment",
        ),
        sa.CheckConstraint(
            "body IS NULL OR (char_length(body) >= 1 AND char_length(body) <= 5000)",
            name="ck_timeline_body_length",
        ),
        sa.CheckConstraint(
            "event_order IN (0, 1)", name="ck_timeline_event_order"
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticket_id",
            "request_id",
            "event_type",
            name="uq_timeline_request_event",
        ),
    )

    op.create_index(
        "ix_timeline_ticket_created",
        "ticket_timeline_entries",
        ["ticket_id", "created_at"],
    )
    op.create_index(
        "ix_timeline_ticket_internal",
        "ticket_timeline_entries",
        ["ticket_id", "is_internal"],
    )
    op.create_index(
        "ix_timeline_author",
        "ticket_timeline_entries",
        ["author_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_author", table_name="ticket_timeline_entries")
    op.drop_index(
        "ix_timeline_ticket_internal", table_name="ticket_timeline_entries"
    )
    op.drop_index(
        "ix_timeline_ticket_created", table_name="ticket_timeline_entries"
    )
    op.drop_table("ticket_timeline_entries")

    bind = op.get_bind()
    timeline_event_type.drop(bind, checkfirst=True)
