from dataclasses import dataclass
from pathlib import Path

from analysis_engine.detection.languages import detect_language, iter_source_files
from analysis_engine.extraction import python_extractor, ts_js_extractor
from analysis_engine.extraction.models import DependencyEdge, Import, Symbol
from analysis_engine.extraction.resolution import resolve_relationships
from analysis_engine.ingestion.clone import (
    RepositoryRef,
    clone_repository,
    enforce_size_cap,
    validate_github_url,
)
from analysis_engine.ingestion.workspace import scratch_workspace
from analysis_engine.parsing import python_parser, ts_js_parser
from analysis_engine.parsing.models import FileSummary


@dataclass(frozen=True)
class AnalysisResult:
    repository: RepositoryRef
    languages: dict[str, int]
    files: list[FileSummary]
    dependency_edges: list[DependencyEdge]
    total_files: int
    total_lines: int


def _parse_file(path: Path, language: str | None) -> tuple[bool | None, int, list[Symbol], list[Import]]:
    """Return (parse_ok, line_count, symbols, imports) for one file.

    parse_ok is None when the file's language has no parser yet. Symbol/
    import extraction only runs once parse_ok is True -- extracting from a
    file tree-sitter/ast already flagged as broken would just produce
    garbage entries.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None, 0, [], []

    line_count = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)

    if language == "python":
        text = raw.decode("utf-8", errors="replace")
        ok = python_parser.parse_ok(text)
        if not ok:
            return ok, line_count, [], []
        extraction = python_extractor.extract(text)
        return ok, line_count, extraction.symbols, extraction.imports

    if language in ("javascript", "typescript"):
        ok = ts_js_parser.parse_ok(raw, path)
        if not ok:
            return ok, line_count, [], []
        extraction = ts_js_extractor.extract(raw, path)
        return ok, line_count, extraction.symbols, extraction.imports

    return None, line_count, [], []


def run_pipeline(repo_url: str, max_size_mb: int, clone_timeout_seconds: int) -> AnalysisResult:
    """Clone, detect languages, parse, and extract top-level symbols +
    import/export edges into a module-level dependency graph.

    This is the entire Day 2 engine surface: no call-graph resolution or
    impact analysis yet (Day 3+). Pure function over the filesystem -- no
    database access, so it stays usable from a CLI or test without a worker.
    """
    ref = validate_github_url(repo_url)

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

        files: list[FileSummary] = []
        files_with_imports: list[tuple[str, str | None, list[Import]]] = []
        total_lines = 0
        for path in iter_source_files(workspace):
            language = detect_language(path)
            parse_ok_value, line_count, symbols, imports = _parse_file(path, language)
            total_lines += line_count
            rel_path = str(path.relative_to(workspace))
            files.append(
                FileSummary(
                    path=rel_path,
                    language=language,
                    line_count=line_count,
                    parse_ok=parse_ok_value,
                    size_bytes=path.stat().st_size,
                    symbols=symbols,
                )
            )
            files_with_imports.append((rel_path, language, imports))

        language_counts: dict[str, int] = {}
        for f in files:
            if f.language:
                language_counts[f.language] = language_counts.get(f.language, 0) + 1

        dependency_edges = resolve_relationships(files_with_imports)

    return AnalysisResult(
        repository=ref,
        languages=language_counts,
        files=files,
        dependency_edges=dependency_edges,
        total_files=len(files),
        total_lines=total_lines,
    )
