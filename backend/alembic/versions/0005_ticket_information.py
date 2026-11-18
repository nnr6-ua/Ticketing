"""Añade las peticiones y respuestas de información (HU-03).

Extiende la línea temporal con los eventos `information_request` y
`user_response`, y con el vínculo autorreferente `reply_to_id`.

Revision ID: 0005_ticket_information
Revises: 0004_ticket_creation
Create Date: 2026-11-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ticket_information"
down_revision: Union[str, None] = "0004_ticket_creation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL exige confirmar los valores nuevos antes de usarlos en CHECK.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE timeline_event_type "
            "ADD VALUE IF NOT EXISTS 'information_request'"
        )
        op.execute(
            "ALTER TYPE timeline_event_type "
            "ADD VALUE IF NOT EXISTS 'user_response'"
        )

    op.add_column(
        "ticket_timeline_entries",
        sa.Column("reply_to_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_timeline_reply_to",
        "ticket_timeline_entries",
        "ticket_timeline_entries",
        ["reply_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_timeline_information_request",
        "ticket_timeline_entries",
        "(event_type <> 'information_request') OR "
        "(from_status IS NULL AND to_status IS NULL "
        "AND body IS NOT NULL AND is_internal = false "
        "AND reply_to_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_timeline_user_response",
        "ticket_timeline_entries",
        "(event_type <> 'user_response') OR "
        "(from_status IS NULL AND to_status IS NULL "
        "AND body IS NOT NULL AND is_internal = false)",
    )
    op.create_index(
        "ix_timeline_reply_to",
        "ticket_timeline_entries",
        ["reply_to_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_reply_to", table_name="ticket_timeline_entries")
    op.drop_constraint(
        "ck_timeline_user_response",
        "ticket_timeline_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_timeline_information_request",
        "ticket_timeline_entries",
        type_="check",
    )
    op.drop_constraint(
        "fk_timeline_reply_to",
        "ticket_timeline_entries",
        type_="foreignkey",
    )
    op.drop_column("ticket_timeline_entries", "reply_to_id")

    # PostgreSQL no permite quitar valores de un ENUM sin recrear el tipo.
    # Se conservan `information_request` y `user_response`: son inocuos para
    # el esquema anterior y preservan la compatibilidad de los datos.
