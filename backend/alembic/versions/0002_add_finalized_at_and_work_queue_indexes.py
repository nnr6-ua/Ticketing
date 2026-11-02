"""Añade `finalized_at`, sus restricciones y los índices de la cola.

Revision ID: 0002_work_queue
Revises: 0001_base_schema
Create Date: 2026-10-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_work_queue"
down_revision: Union[str, None] = "0001_base_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "finalized_at", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
    )

    # Backfill: la fecha del primer paso a estado final. No se sobrescribe si
    # ya existiera (idempotencia del script).
    op.execute(
        """
        UPDATE tickets
           SET finalized_at = COALESCE(closed_at, updated_at)
         WHERE status IN ('resuelto', 'cerrado')
           AND finalized_at IS NULL
        """
    )

    op.create_check_constraint(
        "ck_tickets_finalized_at",
        "tickets",
        "(status IN ('resuelto', 'cerrado') AND finalized_at IS NOT NULL) "
        "OR (status NOT IN ('resuelto', 'cerrado') AND finalized_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_tickets_finalized_after_created",
        "tickets",
        "finalized_at IS NULL OR finalized_at >= created_at",
    )
    op.create_check_constraint(
        "ck_tickets_sla_deadline_after_created",
        "tickets",
        "sla_deadline IS NULL OR sla_deadline > created_at",
    )

    op.create_index(
        "ix_tickets_assignee_status_deadline",
        "tickets",
        ["assignee_id", "status", "sla_deadline"],
    )
    op.create_index(
        "ix_tickets_assignee_priority",
        "tickets",
        ["assignee_id", "priority_id"],
    )
    op.create_index("ix_tickets_number", "tickets", ["number"])
    op.execute(
        "CREATE INDEX ix_tickets_assignee_finalized_at "
        "ON tickets (assignee_id, finalized_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tickets_assignee_finalized_at")
    op.drop_index("ix_tickets_number", table_name="tickets")
    op.drop_index("ix_tickets_assignee_priority", table_name="tickets")
    op.drop_index("ix_tickets_assignee_status_deadline", table_name="tickets")

    op.drop_constraint("ck_tickets_sla_deadline_after_created", "tickets", type_="check")
    op.drop_constraint("ck_tickets_finalized_after_created", "tickets", type_="check")
    op.drop_constraint("ck_tickets_finalized_at", "tickets", type_="check")
    op.drop_column("tickets", "finalized_at")
