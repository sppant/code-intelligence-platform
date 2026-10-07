"""Add symbols and relationships tables (Day 2: AST/tree-sitter symbol
extraction and the module-level dependency graph)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("line_start", sa.Integer, nullable=False),
        sa.Column("line_end", sa.Integer, nullable=False),
    )
    op.create_index("ix_symbols_analysis_id", "symbols", ["analysis_id"])
    op.create_index("ix_symbols_file_id", "symbols", ["file_id"])
    op.create_index("ix_symbols_name", "symbols", ["name"])

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("target_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("type", sa.Text, nullable=False, server_default="imports"),
        sa.Column("external_module", sa.Text, nullable=True),
    )
    op.create_index("ix_relationships_analysis_id", "relationships", ["analysis_id"])
    op.create_index("ix_relationships_source_file_id", "relationships", ["source_file_id"])
    op.create_index("ix_relationships_target_file_id", "relationships", ["target_file_id"])


def downgrade() -> None:
    op.drop_table("relationships")
    op.drop_table("symbols")
