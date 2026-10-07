from dataclasses import dataclass
from pathlib import Path

from analysis_engine.detection.languages import detect_language, iter_source_files
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
    total_files: int
    total_lines: int


def _parse_file(path: Path, language: str | None) -> tuple[bool | None, int]:
    """Return (parse_ok, line_count) for one file. parse_ok is None when the
    file's language has no parser yet (Day 1 only covers python/js/ts)."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None, 0

    line_count = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)

    if language == "python":
        return python_parser.parse_ok(raw.decode("utf-8", errors="replace")), line_count
    if language in ("javascript", "typescript"):
        return ts_js_parser.parse_ok(raw, path), line_count
    return None, line_count


def run_pipeline(repo_url: str, max_size_mb: int, clone_timeout_seconds: int) -> AnalysisResult:
    """Clone, detect languages, and do a shallow per-file parse pass.

    This is the entire Day 1 engine surface: no symbol extraction or
    dependency graph yet (Day 2+). Pure function over the filesystem -- no
    database access, so it stays usable from a CLI or test without a worker.
    """
    ref = validate_github_url(repo_url)

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

        files: list[FileSummary] = []
        total_lines = 0
        for path in iter_source_files(workspace):
            language = detect_language(path)
            parse_ok_value, line_count = _parse_file(path, language)
            total_lines += line_count
            files.append(
                FileSummary(
                    path=str(path.relative_to(workspace)),
                    language=language,
                    line_count=line_count,
                    parse_ok=parse_ok_value,
                    size_bytes=path.stat().st_size,
                )
            )

        language_counts: dict[str, int] = {}
        for f in files:
            if f.language:
                language_counts[f.language] = language_counts.get(f.language, 0) + 1

    return AnalysisResult(
        repository=ref,
        languages=language_counts,
        files=files,
        total_files=len(files),
        total_lines=total_lines,
    )
