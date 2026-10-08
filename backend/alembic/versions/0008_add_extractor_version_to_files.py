"""Add extractor_version to files, so incremental analysis can tell a
content-hash match from a stale (pre-upgrade) extractor apart from a real
cache hit -- see analysis_engine.extraction.models.EXTRACTOR_VERSION and
pipeline.py's _build_file_summary.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("files", sa.Column("extractor_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("files", "extractor_version")
