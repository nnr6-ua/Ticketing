"""Permite comentarios públicos del técnico en la línea temporal (US2).

La restricción existente obligaba a que toda entrada `internal_comment` fuera
interna. Se amplía para admitir también comentarios públicos (`is_internal =
false`), que el usuario creador puede consultar según RN-03. El cambio es
compatible hacia atrás: todas las filas válidas antes siguen siéndolo. El
downgrade conserva los comentarios públicos ya registrados con una restricción
NOT VALID, de modo que las nuevas escrituras vuelven a ser solo internas sin
perder evidencia.

Revision ID: 0005_public_timeline_comments
Revises: 0004_ticket_creation
Create Date: 2026-11-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_public_timeline_comments"
down_revision: Union[str, None] = "0004_ticket_creation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "ticket_timeline_entries"
CONSTRAINT = "ck_timeline_internal_comment"

PRIVATE_ONLY = (
    "(event_type <> 'internal_comment') OR "
    "(from_status IS NULL AND to_status IS NULL "
    "AND body IS NOT NULL AND is_internal = true)"
)
VISIBILITY_AWARE = (
    "(event_type <> 'internal_comment') OR "
    "(from_status IS NULL AND to_status IS NULL AND body IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.create_check_constraint(CONSTRAINT, TABLE, VISIBILITY_AWARE)


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.create_check_constraint(
        CONSTRAINT, TABLE, PRIVATE_ONLY, postgresql_not_valid=True
    )
