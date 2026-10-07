"""Initial schema: repositories, analysis_jobs, analyses, files

Revision ID: 0001
Revises:
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("owner", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("default_branch", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("arq_job_id", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_jobs_repository_id", "analysis_jobs", ["repository_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])

    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.Text, nullable=True),
        sa.Column("languages", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_lines", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analyses_repository_id", "analyses", ["repository_id"])

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id"),
            nullable=False,
        ),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("language", sa.Text, nullable=True),
        sa.Column("line_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parse_ok", sa.Boolean, nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=True),
    )
    op.create_index("ix_files_analysis_id", "files", ["analysis_id"])


def downgrade() -> None:
    op.drop_table("files")
    op.drop_table("analyses")
    op.drop_table("analysis_jobs")
    op.drop_table("repositories")
