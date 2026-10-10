"""Add client_ip to analysis_jobs, so analyzeRepository can be rate-limited
per client IP -- see backend.rate_limit.enforce_rate_limit.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_jobs", sa.Column("client_ip", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_jobs", "client_ip")
