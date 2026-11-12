"""Esquema inicial de la mesa de ayuda.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-29

"""

from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1 INCREMENT 1")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
    op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")
