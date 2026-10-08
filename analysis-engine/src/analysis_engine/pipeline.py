import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from analysis_engine.detection.languages import detect_language, iter_source_files
from analysis_engine.extraction import python_extractor, ts_js_extractor
from analysis_engine.extraction.call_resolution import resolve_calls
from analysis_engine.extraction.models import EXTRACTOR_VERSION, CallEdge, CallSite, DependencyEdge, Import, Symbol
from analysis_engine.extraction.resolution import resolve_relationships
from analysis_engine.ingestion.clone import (
    RepositoryRef,
    clone_repository,
    enforce_size_cap,
    get_commit_sha,
    validate_github_url,
)
from analysis_engine.ingestion.workspace import scratch_workspace
from analysis_engine.parsing import python_parser, ts_js_parser
from analysis_engine.parsing.models import FileSummary


@dataclass(frozen=True)
class WorkspaceAnalysis:
    languages: dict[str, int]
    files: list[FileSummary]
    dependency_edges: list[DependencyEdge]
    call_edges: list[CallEdge]
    total_files: int
    total_lines: int
    is_incremental: bool
    files_reused: int
    files_reprocessed: int


@dataclass(frozen=True)
class AnalysisResult:
    repository: RepositoryRef
    commit_sha: str | None
    languages: dict[str, int]
    files: list[FileSummary]
    dependency_edges: list[DependencyEdge]
    call_edges: list[CallEdge]
    total_files: int
    total_lines: int
    is_incremental: bool
    files_reused: int
    files_reprocessed: int


def _hash_file(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_file(
    path: Path, language: str | None, raw: bytes
) -> tuple[bool | None, list[Symbol], list[Import], list[CallSite]]:
    """Return (parse_ok, symbols, imports, calls) for one file's already-read
    bytes. parse_ok is None when the file's language has no parser yet.
    Symbol/import/call extraction only runs once parse_ok is True --
    extracting from a file tree-sitter/ast already flagged as broken would
    just produce garbage entries. Only called when a file can't be reused
    from a previous analysis (see _build_file_summary).
    """
    if language == "python":
        text = raw.decode("utf-8", errors="replace")
        ok = python_parser.parse_ok(text)
        if not ok:
            return ok, [], [], []
        extraction = python_extractor.extract(text)
        return ok, extraction.symbols, extraction.imports, extraction.calls

    if language in ("javascript", "typescript"):
        ok = ts_js_parser.parse_ok(raw, path)
        if not ok:
            return ok, [], [], []
        extraction = ts_js_extractor.extract(raw, path)
        return ok, extraction.symbols, extraction.imports, extraction.calls

    return None, [], [], []


def _build_file_summary(
    path: Path, rel_path: str, language: str | None, previous: FileSummary | None
) -> tuple[FileSummary, bool]:
    """Read one file and either reuse a previous analysis's parse/extraction
    result (when its content hash is unchanged) or parse+extract fresh.

    Returns (summary, reused). Reuse skips ast.parse/tree-sitter-parse and
    symbol/import/call extraction entirely -- confirmed as the expensive
    step both parsers+extractors do (each re-parses from scratch today).
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return FileSummary(rel_path, language, 0, None, 0, [], None, [], []), False

    line_count = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)
    content_hash = _hash_file(raw)
    size_bytes = len(raw)

    if (
        previous is not None
        and previous.content_hash == content_hash
        and previous.extractor_version == EXTRACTOR_VERSION
    ):
        return (
            FileSummary(
                path=rel_path,
                language=language,
                line_count=line_count,
                parse_ok=previous.parse_ok,
                size_bytes=size_bytes,
                symbols=previous.symbols,
                content_hash=content_hash,
                imports=previous.imports,
                calls=previous.calls,
                extractor_version=previous.extractor_version,
            ),
            True,
        )

    parse_ok_value, symbols, imports, calls = _parse_file(path, language, raw)
    return (
        FileSummary(
            path=rel_path,
            language=language,
            line_count=line_count,
            parse_ok=parse_ok_value,
            size_bytes=size_bytes,
            symbols=symbols,
            content_hash=content_hash,
            imports=imports,
            calls=calls,
            extractor_version=EXTRACTOR_VERSION,
        ),
        False,
    )


def analyze_workspace(
    workspace: Path,
    on_progress: Callable[[str], None] | None = None,
    previous_files: dict[str, FileSummary] | None = None,
) -> WorkspaceAnalysis:
    """Detect languages, parse, and extract top-level symbols, the module-
    level import dependency graph, and the (same-file + import-resolved)
    call graph for an already-cloned (or otherwise assembled) directory.

    `previous_files`, if given, maps repo-relative path -> that file's
    FileSummary from a previous analysis (including its cached imports/
    calls, not just resolved edges). A file whose content hash matches its
    previous run is reused verbatim, skipping parse+extraction. Resolution
    (`resolve_relationships`/`resolve_calls`) always runs over the FULL
    current file set regardless of what was reused -- a changed file's
    import might newly resolve to an unchanged file, and an unchanged
    file's previously-resolved import must correctly become unresolved if
    its target was deleted elsewhere, so there is no dangling-edge risk
    from this design (unlike carrying forward previously-resolved edges
    directly would have).

    Split out from run_pipeline specifically so it's testable against a
    plain temp directory, with no network clone involved.
    """
    if on_progress:
        # Language detection happens per-file inside the loop below, not as
        # a separate pass -- firing a distinct "detecting languages" stage
        # here would be a phantom stage with zero real work before the very
        # next one, so it's folded into this one.
        on_progress("parsing_and_extracting")

    files: list[FileSummary] = []
    total_lines = 0
    files_reused = 0
    for path in iter_source_files(workspace):
        language = detect_language(path)
        rel_path = str(path.relative_to(workspace))
        previous = previous_files.get(rel_path) if previous_files else None
        summary, reused = _build_file_summary(path, rel_path, language, previous)
        files.append(summary)
        total_lines += summary.line_count
        if reused:
            files_reused += 1

    language_counts: dict[str, int] = {}
    for f in files:
        if f.language:
            language_counts[f.language] = language_counts.get(f.language, 0) + 1

    if on_progress:
        on_progress("resolving_imports")
    # Built from `files` AFTER the loop (reused + reprocessed together) --
    # this is what makes reuse safe: resolution sees every file's imports
    # regardless of whether they came from cache or fresh extraction.
    files_with_imports = [(f.path, f.language, f.imports) for f in files]
    dependency_edges = resolve_relationships(files_with_imports)

    if on_progress:
        on_progress("building_call_graph")
    files_with_calls = [(f.path, f.language, f.symbols, f.imports, f.calls) for f in files]
    call_edges = resolve_calls(files_with_calls)

    return WorkspaceAnalysis(
        languages=language_counts,
        files=files,
        dependency_edges=dependency_edges,
        call_edges=call_edges,
        total_files=len(files),
        total_lines=total_lines,
        is_incremental=previous_files is not None,
        files_reused=files_reused,
        files_reprocessed=len(files) - files_reused,
    )


def run_pipeline(
    repo_url: str,
    max_size_mb: int,
    clone_timeout_seconds: int,
    on_progress: Callable[[str], None] | None = None,
    previous_files: dict[str, FileSummary] | None = None,
) -> AnalysisResult:
    """Clone a repository and analyze it (see analyze_workspace).

    `on_progress`, if given, is called synchronously with a short stage name
    at each major step: "cloning", then (inside analyze_workspace)
    "parsing_and_extracting", "resolving_imports", "building_call_graph".
    Purely informational -- this function has no database access, so it
    remains usable from a CLI or test without a worker. "persisting" is
    never fired here; the caller (jobs/tasks.py) sets that stage itself
    once this function returns.

    No method/attribute-call resolution and no impact analysis yet (those
    live in analysis_engine.graph, computed over this result's edges by the
    caller).
    """
    ref = validate_github_url(repo_url)

    if on_progress:
        on_progress("cloning")

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        commit_sha = get_commit_sha(workspace)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

        ws = analyze_workspace(workspace, on_progress, previous_files)

    return AnalysisResult(
        repository=ref,
        commit_sha=commit_sha,
        languages=ws.languages,
        files=ws.files,
        dependency_edges=ws.dependency_edges,
        call_edges=ws.call_edges,
        total_files=ws.total_files,
        total_lines=ws.total_lines,
        is_incremental=ws.is_incremental,
        files_reused=ws.files_reused,
        files_reprocessed=ws.files_reprocessed,
    )
