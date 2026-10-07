from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str  # "function" | "class" | "variable" | "interface" | "type_alias"
    line_start: int
    line_end: int


@dataclass(frozen=True)
class Import:
    module: str  # dotted path (python) or raw specifier (ts/js)
    level: int  # python: 0 = absolute, >=1 = relative dot-count. ts/js: always 0
    line: int


@dataclass(frozen=True)
class FileExtraction:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)


@dataclass(frozen=True)
class DependencyEdge:
    source_path: str
    target_path: str | None  # None => unresolved/external
    external_module: str | None  # raw specifier when target_path is None, else None
    type: str = "imports"  # Day 2 only ever emits "imports" -- "calls" is Day 3
