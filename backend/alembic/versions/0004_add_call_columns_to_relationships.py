"""Add symbol-level call-graph columns to relationships (Day 3: call-graph
extraction -- type="calls" rows reuse the existing table per the class's
own forward-looking comment from Day 2)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "relationships",
        sa.Column("source_symbol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("symbols.id"), nullable=True),
    )
    op.add_column(
        "relationships",
        sa.Column("target_symbol_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("symbols.id"), nullable=True),
    )
    op.add_column("relationships", sa.Column("called_name", sa.Text, nullable=True))
    op.create_index("ix_relationships_source_symbol_id", "relationships", ["source_symbol_id"])
    op.create_index("ix_relationships_target_symbol_id", "relationships", ["target_symbol_id"])


def downgrade() -> None:
    op.drop_index("ix_relationships_target_symbol_id", table_name="relationships")
    op.drop_index("ix_relationships_source_symbol_id", table_name="relationships")
    op.drop_column("relationships", "called_name")
    op.drop_column("relationships", "target_symbol_id")
    op.drop_column("relationships", "source_symbol_id")
