"""Añade el soporte de creación de tickets (HU-01).

Incluye las columnas de sugerencia de catálogos, el hash de contenido para
detectar duplicados, la tabla de adjuntos, la secuencia de numeración y el
tipo de evento `created` de la línea temporal.

Revision ID: 0004_ticket_creation
Revises: 0003_ticket_timeline
Create Date: 2026-11-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ticket_creation"
down_revision: Union[str, None] = "0003_ticket_timeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Nuevo evento de la línea temporal para registrar la creación.
    op.execute(
        "ALTER TYPE timeline_event_type ADD VALUE IF NOT EXISTS 'created'"
    )

    # Catálogos: palabras clave y orden para las sugerencias automáticas.
    op.add_column(
        "categories",
        sa.Column(
            "keywords", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )

    op.add_column(
        "priorities",
        sa.Column(
            "keywords", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )
    op.add_column(
        "priorities",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "priorities",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "priorities",
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )

    # Hash de contenido por creador para detectar duplicados.
    op.add_column(
        "tickets",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_tickets_creator_content_hash",
        "tickets",
        ["creator_id", "content_hash"],
    )

    # Secuencia usada para numerar tickets en PostgreSQL.
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1 INCREMENT 1"
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/gif')",
            name="ck_attachments_mime_type",
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 5242880",
            name="ck_attachments_size",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
        sa.UniqueConstraint("relative_path"),
    )
    op.create_index("ix_attachments_ticket", "attachments", ["ticket_id"])

    _ = bind  # El enlace se mantiene por compatibilidad de firmas.


def downgrade() -> None:
    op.drop_index("ix_attachments_ticket", table_name="attachments")
    op.drop_table("attachments")

    op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")

    op.drop_constraint(
        "uq_tickets_creator_content_hash", "tickets", type_="unique"
    )
    op.drop_column("tickets", "content_hash")

    for table in ("categories", "priorities"):
        op.drop_column(table, "sort_order")
        op.drop_column(table, "is_system")
        op.drop_column(table, "is_default")
        op.drop_column(table, "keywords")

    # PostgreSQL no permite eliminar un valor de un ENUM de forma sencilla.
    # El valor `created` es inocuo para versiones anteriores.
