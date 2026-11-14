"""Cambio de responsable: niveles, línea temporal y notificaciones (HU-06).

Revision ID: 0004_assignee_changes
Revises: 0003_ticket_timeline
Create Date: 2026-11-12

Migración aditiva salvo por el nuevo valor del enum `timeline_event_type`.
`downgrade()` es **destructivo**: elimina las notificaciones, las entradas
`assignee_change` y la columna `users.escalation_level`. Requiere copia de
seguridad antes de ejecutarlo en producción.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_assignee_changes"
down_revision: Union[str, None] = "0003_ticket_timeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

escalation_level = postgresql.ENUM(
    "nivel_1", "nivel_2", "especialista", name="escalation_level", create_type=False
)
assignee_change_kind = postgresql.ENUM(
    "reassignment", "escalation", name="assignee_change_kind", create_type=False
)
notification_type = postgresql.ENUM(
    "ticket_reassigned", "ticket_escalated", name="notification_type", create_type=False
)
timeline_event_type = postgresql.ENUM(
    "status_change",
    "resolution",
    "internal_comment",
    "assignee_change",
    name="timeline_event_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    escalation_level.create(bind, checkfirst=True)
    assignee_change_kind.create(bind, checkfirst=True)
    notification_type.create(bind, checkfirst=True)

    # PostgreSQL exige ejecutar `ALTER TYPE ... ADD VALUE` fuera de la
    # transacción de la migración (antes de PG 12 no podía usarse el nuevo
    # valor en la misma transacción).
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE timeline_event_type ADD VALUE IF NOT EXISTS 'assignee_change'"
        )

    op.add_column(
        "users",
        sa.Column(
            "escalation_level",
            escalation_level,
            nullable=False,
            server_default="nivel_1",
        ),
    )
    op.create_index(
        "ix_users_role_active_level_team",
        "users",
        ["role", "is_active", "escalation_level", "team"],
    )

    op.add_column(
        "ticket_timeline_entries",
        sa.Column("previous_assignee_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ticket_timeline_entries",
        sa.Column("new_assignee_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ticket_timeline_entries",
        sa.Column("change_kind", assignee_change_kind, nullable=True),
    )
    op.add_column(
        "ticket_timeline_entries",
        sa.Column("from_escalation_level", escalation_level, nullable=True),
    )
    op.add_column(
        "ticket_timeline_entries",
        sa.Column("to_escalation_level", escalation_level, nullable=True),
    )
    op.create_foreign_key(
        "fk_timeline_previous_assignee",
        "ticket_timeline_entries",
        "users",
        ["previous_assignee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_timeline_new_assignee",
        "ticket_timeline_entries",
        "users",
        ["new_assignee_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_timeline_assignee_change",
        "ticket_timeline_entries",
        "(event_type <> 'assignee_change') OR ("
        "body IS NOT NULL "
        "AND is_internal = false "
        "AND from_status IS NULL "
        "AND to_status IS NULL "
        "AND previous_assignee_id IS NOT NULL "
        "AND new_assignee_id IS NOT NULL "
        "AND previous_assignee_id <> new_assignee_id "
        "AND change_kind IS NOT NULL "
        "AND from_escalation_level IS NOT NULL "
        "AND to_escalation_level IS NOT NULL "
        "AND ("
        "(change_kind = 'reassignment' "
        "AND from_escalation_level = to_escalation_level) "
        "OR (change_kind = 'escalation' "
        "AND from_escalation_level <> to_escalation_level)"
        "))",
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("timeline_entry_id", sa.Uuid(), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("ticket_number", sa.String(length=20), nullable=False),
        sa.Column("ticket_title", sa.String(length=200), nullable=False),
        sa.Column("previous_assignee_name", sa.String(length=150), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "read_at", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "(is_read = false AND read_at IS NULL) OR "
            "(is_read = true AND read_at IS NOT NULL)",
            name="ck_notifications_read_at",
        ),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["timeline_entry_id"],
            ["ticket_timeline_entries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "timeline_entry_id", name="uq_notifications_timeline_entry"
        ),
    )
    op.create_index(
        "ix_notifications_recipient_read_created",
        "notifications",
        ["recipient_id", "is_read", "created_at"],
    )
    op.create_index(
        "ix_notifications_ticket", "notifications", ["ticket_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_ticket", table_name="notifications")
    op.drop_index(
        "ix_notifications_recipient_read_created", table_name="notifications"
    )
    op.drop_table("notifications")

    op.drop_constraint(
        "ck_timeline_assignee_change",
        "ticket_timeline_entries",
        type_="check",
    )
    op.drop_constraint(
        "fk_timeline_previous_assignee",
        "ticket_timeline_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_timeline_new_assignee",
        "ticket_timeline_entries",
        type_="foreignkey",
    )
    op.drop_column("ticket_timeline_entries", "to_escalation_level")
    op.drop_column("ticket_timeline_entries", "from_escalation_level")
    op.drop_column("ticket_timeline_entries", "change_kind")
    op.drop_column("ticket_timeline_entries", "new_assignee_id")
    op.drop_column("ticket_timeline_entries", "previous_assignee_id")

    op.execute(
        "DELETE FROM ticket_timeline_entries "
        "WHERE event_type = 'assignee_change'"
    )

    # Las restricciones CHECK de HU-05 comparan `event_type` con literales del
    # enum `timeline_event_type`. PostgreSQL las revalida al cambiar el tipo de
    # la columna, así que deben eliminarse antes de convertirla a `text` y
    # recrearse después con el enum reducido.
    for constraint in (
        "ck_timeline_status_change",
        "ck_timeline_resolution",
        "ck_timeline_internal_comment",
    ):
        op.drop_constraint(
            constraint, "ticket_timeline_entries", type_="check"
        )

    # PostgreSQL no permite eliminar un valor de enum: se recrea el tipo sin
    # `assignee_change` y se vuelve a aplicar a la columna.
    op.execute(
        "ALTER TABLE ticket_timeline_entries "
        "ALTER COLUMN event_type TYPE text USING event_type::text"
    )
    op.execute("DROP TYPE timeline_event_type")
    op.execute(
        "CREATE TYPE timeline_event_type AS ENUM "
        "('status_change', 'resolution', 'internal_comment')"
    )
    op.execute(
        "ALTER TABLE ticket_timeline_entries "
        "ALTER COLUMN event_type TYPE timeline_event_type "
        "USING event_type::timeline_event_type"
    )

    op.create_check_constraint(
        "ck_timeline_status_change",
        "ticket_timeline_entries",
        "(event_type <> 'status_change') OR "
        "(from_status IS NOT NULL AND to_status IS NOT NULL "
        "AND from_status <> to_status AND body IS NULL "
        "AND is_internal = false)",
    )
    op.create_check_constraint(
        "ck_timeline_resolution",
        "ticket_timeline_entries",
        "(event_type <> 'resolution') OR "
        "(to_status = 'resuelto' AND body IS NOT NULL "
        "AND is_internal = false)",
    )
    op.create_check_constraint(
        "ck_timeline_internal_comment",
        "ticket_timeline_entries",
        "(event_type <> 'internal_comment') OR "
        "(from_status IS NULL AND to_status IS NULL "
        "AND body IS NOT NULL AND is_internal = true)",
    )

    op.drop_index("ix_users_role_active_level_team", table_name="users")
    op.drop_column("users", "escalation_level")

    bind = op.get_bind()
    notification_type.drop(bind, checkfirst=True)
    assignee_change_kind.drop(bind, checkfirst=True)
    escalation_level.drop(bind, checkfirst=True)
