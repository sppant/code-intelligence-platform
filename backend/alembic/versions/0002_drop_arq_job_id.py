"""Drop analysis_jobs.arq_job_id (dead column -- arq/Redis removed in favor
of an in-process background task + cron sweep; see jobs/claims.py)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("analysis_jobs", "arq_job_id")


def downgrade() -> None:
    op.add_column("analysis_jobs", sa.Column("arq_job_id", sa.Text, nullable=True))
