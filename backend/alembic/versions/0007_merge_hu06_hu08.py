"""Fusión de las ramas de migraciones de HU-06 y HU-08.

Revision ID: 0007_merge_hu06_hu08
Revises: 0004_assignee_changes, 0006_sla_configuration
Create Date: 2026-11-17
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "0007_merge_hu06_hu08"
down_revision: Union[str, tuple[str, ...], None] = (
    "0004_assignee_changes",
    "0006_sla_configuration",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Solo unifica el historial; ambas ramas ya aplicaron sus cambios."""


def downgrade() -> None:
    """No hay cambios propios que revertir."""
