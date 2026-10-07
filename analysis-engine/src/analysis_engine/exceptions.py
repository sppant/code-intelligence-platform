class AnalysisEngineError(Exception):
    """Base class for all analysis-engine errors."""


class InvalidRepositoryUrlError(AnalysisEngineError):
    """Raised when a repository URL fails validation."""


class CloneTimeoutError(AnalysisEngineError):
    """Raised when cloning a repository exceeds the configured timeout."""


class CloneFailedError(AnalysisEngineError):
    """Raised when `git clone` exits non-zero."""


class RepositoryTooLargeError(AnalysisEngineError):
    """Raised when a cloned repository exceeds the configured size cap."""
