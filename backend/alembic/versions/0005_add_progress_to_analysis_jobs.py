"""Add progress column to analysis_jobs (Day 3: lightweight polled job
progress, no new infra -- see jobs/tasks.py's on_progress threading)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_jobs", sa.Column("progress", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_jobs", "progress")
