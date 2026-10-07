from dataclasses import dataclass

from analysis_engine.detection.languages import detect_language, iter_source_files
from analysis_engine.ingestion.clone import (
    RepositoryRef,
    clone_repository,
    enforce_size_cap,
    validate_github_url,
)
from analysis_engine.ingestion.workspace import scratch_workspace


@dataclass(frozen=True)
class FileSummary:
    path: str  # relative to repository root
    language: str | None


@dataclass(frozen=True)
class AnalysisResult:
    repository: RepositoryRef
    languages: dict[str, int]
    files: list[FileSummary]
    total_files: int


def run_pipeline(repo_url: str, max_size_mb: int, clone_timeout_seconds: int) -> AnalysisResult:
    """Clone and detect languages present in the repository.

    Per-file parsing (and the parse_ok/line_count fields it produces) is
    added in the next commit.
    """
    ref = validate_github_url(repo_url)

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

        files: list[FileSummary] = []
        for path in iter_source_files(workspace):
            language = detect_language(path)
            files.append(FileSummary(path=str(path.relative_to(workspace)), language=language))

        language_counts: dict[str, int] = {}
        for f in files:
            if f.language:
                language_counts[f.language] = language_counts.get(f.language, 0) + 1

    return AnalysisResult(
        repository=ref,
        languages=language_counts,
        files=files,
        total_files=len(files),
    )
