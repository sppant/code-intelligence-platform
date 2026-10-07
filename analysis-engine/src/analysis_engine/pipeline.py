from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from analysis_engine.detection.languages import detect_language, iter_source_files
from analysis_engine.extraction import python_extractor, ts_js_extractor
from analysis_engine.extraction.call_resolution import resolve_calls
from analysis_engine.extraction.models import CallEdge, CallSite, DependencyEdge, Import, Symbol
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
    call_edges: list[CallEdge]
    total_files: int
    total_lines: int


def _parse_file(
    path: Path, language: str | None
) -> tuple[bool | None, int, list[Symbol], list[Import], list[CallSite]]:
    """Return (parse_ok, line_count, symbols, imports, calls) for one file.

    parse_ok is None when the file's language has no parser yet. Symbol/
    import/call extraction only runs once parse_ok is True -- extracting
    from a file tree-sitter/ast already flagged as broken would just
    produce garbage entries.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None, 0, [], [], []

    line_count = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)

    if language == "python":
        text = raw.decode("utf-8", errors="replace")
        ok = python_parser.parse_ok(text)
        if not ok:
            return ok, line_count, [], [], []
        extraction = python_extractor.extract(text)
        return ok, line_count, extraction.symbols, extraction.imports, extraction.calls

    if language in ("javascript", "typescript"):
        ok = ts_js_parser.parse_ok(raw, path)
        if not ok:
            return ok, line_count, [], [], []
        extraction = ts_js_extractor.extract(raw, path)
        return ok, line_count, extraction.symbols, extraction.imports, extraction.calls

    return None, line_count, [], [], []


def run_pipeline(
    repo_url: str,
    max_size_mb: int,
    clone_timeout_seconds: int,
    on_progress: Callable[[str], None] | None = None,
) -> AnalysisResult:
    """Clone, detect languages, parse, and extract top-level symbols, the
    module-level import dependency graph, and the (same-file + import-
    resolved) call graph.

    `on_progress`, if given, is called synchronously with a short stage name
    at each major step: "cloning", "parsing_and_extracting" (language
    detection + parsing + symbol/import/call extraction, all interleaved in
    the per-file loop below -- deliberately one stage, not several, since
    splitting a single interleaved loop into separately-fired stages would
    misrepresent actual progress), "resolving_imports", and
    "building_call_graph". Purely informational -- this function stays
    otherwise unchanged and still has no database access, so it remains
    usable from a CLI or test without a worker. "persisting" is never fired
    here; the engine has no DB access by design, so the caller
    (jobs/tasks.py) sets that stage itself once this function returns.

    No method/attribute-call resolution and no impact analysis yet (those
    live in analysis_engine.graph, computed over this result's edges by the
    caller).
    """
    ref = validate_github_url(repo_url)

    if on_progress:
        on_progress("cloning")

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

        if on_progress:
            # Language detection happens per-file inside the loop below,
            # not as a separate pass -- firing a distinct "detecting
            # languages" stage here would be a phantom stage with zero real
            # work before the very next one, so it's folded into this one.
            on_progress("parsing_and_extracting")

        files: list[FileSummary] = []
        files_with_imports: list[tuple[str, str | None, list[Import]]] = []
        files_with_calls: list[tuple[str, str | None, list[Symbol], list[Import], list[CallSite]]] = []
        total_lines = 0
        for path in iter_source_files(workspace):
            language = detect_language(path)
            parse_ok_value, line_count, symbols, imports, calls = _parse_file(path, language)
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
            files_with_calls.append((rel_path, language, symbols, imports, calls))

        language_counts: dict[str, int] = {}
        for f in files:
            if f.language:
                language_counts[f.language] = language_counts.get(f.language, 0) + 1

        if on_progress:
            on_progress("resolving_imports")
        dependency_edges = resolve_relationships(files_with_imports)

        if on_progress:
            on_progress("building_call_graph")
        call_edges = resolve_calls(files_with_calls)

    return AnalysisResult(
        repository=ref,
        languages=language_counts,
        files=files,
        dependency_edges=dependency_edges,
        call_edges=call_edges,
        total_files=len(files),
        total_lines=total_lines,
    )
