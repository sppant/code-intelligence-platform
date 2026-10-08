import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis_engine.extraction.models import Symbol as EngineSymbol
from analysis_engine.extraction.serialization import call_site_from_dict, import_from_dict
from analysis_engine.parsing.models import FileSummary
from backend.models import Analysis, AnalysisJob, File
from backend.models import Symbol as SymbolModel


async def load_previous_files(session: AsyncSession, repository_id: uuid.UUID) -> dict[str, FileSummary]:
    """Reconstruct the most recent COMPLETED analysis's files for this
    repository into engine FileSummary objects, keyed by path, for
    pipeline.run_pipeline's `previous_files` parameter.

    Returns {} (not None) when there's no prior completed analysis -- the
    caller (jobs/tasks.py) is responsible for turning that into None before
    passing it to run_pipeline, since {} must NOT be treated as "there was
    an incremental baseline."
    """
    previous_analysis = await session.scalar(
        select(Analysis)
        .join(AnalysisJob, AnalysisJob.id == Analysis.analysis_job_id)
        .where(Analysis.repository_id == repository_id, AnalysisJob.status == "completed")
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    if previous_analysis is None:
        return {}

    file_rows = (await session.scalars(select(File).where(File.analysis_id == previous_analysis.id))).all()
    symbol_rows = (await session.scalars(select(SymbolModel).where(SymbolModel.analysis_id == previous_analysis.id))).all()

    symbols_by_file_id: dict[uuid.UUID, list[EngineSymbol]] = {}
    for s in symbol_rows:
        symbols_by_file_id.setdefault(s.file_id, []).append(
            EngineSymbol(name=s.name, kind=s.kind, line_start=s.line_start, line_end=s.line_end, parent=s.parent)
        )

    previous_files: dict[str, FileSummary] = {}
    for f in file_rows:
        if f.content_hash is None:
            continue  # pre-migration row: nothing to reuse from
        previous_files[f.path] = FileSummary(
            path=f.path,
            language=f.language,
            line_count=f.line_count,
            parse_ok=f.parse_ok,
            size_bytes=f.size_bytes or 0,
            symbols=symbols_by_file_id.get(f.id, []),
            content_hash=f.content_hash,
            imports=[import_from_dict(d) for d in (f.raw_imports or [])],
            calls=[call_site_from_dict(d) for d in (f.raw_calls or [])],
            extractor_version=f.extractor_version,
        )
    return previous_files
