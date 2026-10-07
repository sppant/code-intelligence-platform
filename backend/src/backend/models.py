import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(unique=True)
    owner: Mapped[str]
    name: Mapped[str]
    default_branch: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="repository")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    status: Mapped[str] = mapped_column(default="pending")
    error_message: Mapped[str | None] = mapped_column(default=None)
    arq_job_id: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    repository: Mapped["Repository"] = relationship(back_populates="analysis_jobs")
    analysis: Mapped["Analysis | None"] = relationship(back_populates="analysis_job")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_jobs.id"))
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    commit_sha: Mapped[str | None] = mapped_column(default=None)
    languages: Mapped[dict] = mapped_column(JSON, default=dict)
    total_files: Mapped[int] = mapped_column(default=0)
    total_lines: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    analysis_job: Mapped["AnalysisJob"] = relationship(back_populates="analysis")
    files: Mapped[list["File"]] = relationship(back_populates="analysis")


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"))
    path: Mapped[str]
    language: Mapped[str | None] = mapped_column(default=None)
    line_count: Mapped[int] = mapped_column(default=0)
    parse_ok: Mapped[bool | None] = mapped_column(default=None)
    size_bytes: Mapped[int | None] = mapped_column(default=None)

    analysis: Mapped["Analysis"] = relationship(back_populates="files")
