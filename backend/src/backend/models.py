import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, func
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
    progress: Mapped[str | None] = mapped_column(default=None)
    # The client IP that requested this job, for rate limiting (see
    # backend.rate_limit.enforce_rate_limit) -- nullable because it can't
    # always be determined (e.g. a direct schema.execute call with no
    # underlying HTTP request, as in tests) and rows from before this
    # column existed have nothing to backfill it with.
    client_ip: Mapped[str | None] = mapped_column(default=None)
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
    is_incremental: Mapped[bool] = mapped_column(default=False)
    files_reused: Mapped[int | None] = mapped_column(default=None)
    files_reprocessed: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    analysis_job: Mapped["AnalysisJob"] = relationship(back_populates="analysis")
    files: Mapped[list["File"]] = relationship(back_populates="analysis")
    symbols: Mapped[list["Symbol"]] = relationship(viewonly=True)
    dependency_edges: Mapped[list["DependencyEdge"]] = relationship(viewonly=True)


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"))
    path: Mapped[str]
    language: Mapped[str | None] = mapped_column(default=None)
    line_count: Mapped[int] = mapped_column(default=0)
    parse_ok: Mapped[bool | None] = mapped_column(default=None)
    size_bytes: Mapped[int | None] = mapped_column(default=None)

    # Incremental-analysis cache: content_hash lets the next analysis detect
    # this file is unchanged; raw_imports/raw_calls (not just resolved
    # edges) let that next run feed this file's extraction straight back
    # into resolve_relationships/resolve_calls without re-parsing. Nullable
    # because rows from before this column existed have nothing to reuse.
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    raw_imports: Mapped[list | None] = mapped_column(JSON, default=None)
    raw_calls: Mapped[list | None] = mapped_column(JSON, default=None)
    # Which analysis_engine.extraction.models.EXTRACTOR_VERSION produced
    # raw_imports/raw_calls -- an incremental re-run must not reuse a
    # content-hash match from an OLDER version (see pipeline.py's
    # _build_file_summary), or upgrading the engine would silently keep
    # serving pre-upgrade extraction results forever for already-analyzed
    # repositories.
    extractor_version: Mapped[int | None] = mapped_column(default=None)

    analysis: Mapped["Analysis"] = relationship(back_populates="files")
    symbols: Mapped[list["Symbol"]] = relationship(back_populates="file")


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    name: Mapped[str]
    kind: Mapped[str]
    line_start: Mapped[int]
    line_end: Mapped[int]
    # Enclosing class name for kind="method", NULL for everything else --
    # see analysis_engine.extraction.models.Symbol.parent.
    parent: Mapped[str | None] = mapped_column(default=None)

    file: Mapped["File"] = relationship(back_populates="symbols")


class DependencyEdge(Base):
    """A module-level dependency edge (currently always type="imports";
    target_file_id is nullable specifically so a later "calls" edge type and
    circular-dependency detection can add more rows here without a schema
    change). Table name stays "relationships" to match the conceptual model
    in the spec, but the class is named DependencyEdge -- not Relationship
    -- to avoid colliding in spirit with SQLAlchemy's own relationship()
    used throughout this module for ORM back-refs.
    """

    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"))
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    target_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), default=None)
    type: Mapped[str] = mapped_column(default="imports")
    external_module: Mapped[str | None] = mapped_column(default=None)

    # type="calls" only (Day 3): the specific symbols involved, and the raw
    # call-site text (may differ from target symbol's own name on an alias).
    # Not reused from external_module, which means something different (an
    # unresolved *import* specifier).
    source_symbol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("symbols.id"), default=None)
    target_symbol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("symbols.id"), default=None)
    called_name: Mapped[str | None] = mapped_column(default=None)
