from dataclasses import dataclass, field

from analysis_engine.extraction.models import Symbol


@dataclass(frozen=True)
class FileSummary:
    path: str  # relative to repository root
    language: str | None
    line_count: int
    parse_ok: bool | None  # None when the file's language has no parser yet
    size_bytes: int
    symbols: list[Symbol] = field(default_factory=list)
