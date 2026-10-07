"""Add incremental-analysis support: content_hash + cached raw imports/calls
on files, plus is_incremental/files_reused/files_reprocessed on analyses so
the feature is visible, not just a backend-internal optimization (see
jobs/incremental.py and pipeline.py's previous_files parameter)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("files", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("files", sa.Column("raw_imports", postgresql.JSONB, nullable=True))
    op.add_column("files", sa.Column("raw_calls", postgresql.JSONB, nullable=True))

    op.add_column(
        "analyses",
        sa.Column("is_incremental", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("analyses", sa.Column("files_reused", sa.Integer, nullable=True))
    op.add_column("analyses", sa.Column("files_reprocessed", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "files_reprocessed")
    op.drop_column("analyses", "files_reused")
    op.drop_column("analyses", "is_incremental")
    op.drop_column("files", "raw_calls")
    op.drop_column("files", "raw_imports")
    op.drop_column("files", "content_hash")
