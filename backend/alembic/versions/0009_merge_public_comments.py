"""Fusión de las ramas de migraciones de HU-02 y la línea principal.

Revision ID: 0009_merge_public_comments
Revises: 0008_sync_ticket_number_sequence, 0005_public_timeline_comments
Create Date: 2026-11-18
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "0009_merge_public_comments"
down_revision: Union[str, tuple[str, ...], None] = (
    "0008_sync_ticket_number_sequence",
    "0005_public_timeline_comments",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Solo unifica el historial; ambas ramas ya aplicaron sus cambios."""


def downgrade() -> None:
    """No hay cambios propios que revertir."""
