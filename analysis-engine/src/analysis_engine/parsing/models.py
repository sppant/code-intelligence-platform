from dataclasses import dataclass, field

from analysis_engine.extraction.models import CallSite, Import, Symbol


@dataclass(frozen=True)
class FileSummary:
    path: str  # relative to repository root
    language: str | None
    line_count: int
    parse_ok: bool | None  # None when the file's language has no parser yet
    size_bytes: int
    symbols: list[Symbol] = field(default_factory=list)
    content_hash: str | None = None  # sha256 hex digest; None only for an unreadable file
    imports: list[Import] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    # Which EXTRACTOR_VERSION produced symbols/imports/calls -- None for a
    # file with no parser (content_hash set, nothing extracted) or a
    # pre-migration row. See extraction.models.EXTRACTOR_VERSION.
    extractor_version: int | None = None
