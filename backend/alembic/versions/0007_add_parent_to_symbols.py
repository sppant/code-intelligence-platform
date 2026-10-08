"""Add parent (enclosing class name) to symbols, for nested method
extraction -- see analysis_engine.extraction.models.Symbol.parent and
jobs/incremental.py's reconstruction of cached symbols for reuse.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("symbols", sa.Column("parent", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("symbols", "parent")
