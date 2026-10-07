from dataclasses import dataclass

from analysis_engine.ingestion.clone import (
    RepositoryRef,
    clone_repository,
    enforce_size_cap,
    validate_github_url,
)
from analysis_engine.ingestion.workspace import scratch_workspace


@dataclass(frozen=True)
class AnalysisResult:
    repository: RepositoryRef


def run_pipeline(repo_url: str, max_size_mb: int, clone_timeout_seconds: int) -> AnalysisResult:
    """Clone and validate a repository.

    Language detection and parsing are layered on top in subsequent commits
    -- this is the minimal pipeline that proves the ingestion step end to end.
    """
    ref = validate_github_url(repo_url)

    with scratch_workspace() as workspace:
        clone_repository(ref, workspace, timeout_seconds=clone_timeout_seconds)
        enforce_size_cap(workspace, max_size_mb=max_size_mb)

    return AnalysisResult(repository=ref)
