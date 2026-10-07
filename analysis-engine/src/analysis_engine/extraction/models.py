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
    local_name: str | None = None  # name bound at the call site in THIS file
    imported_name: str | None = None  # original name in the TARGET module (differs from local_name only on `as`)
    is_star: bool = False  # `from x import *` -- deliberately unresolvable for call resolution


@dataclass(frozen=True)
class CallSite:
    callee_name: str
    line: int
    containing_symbol: str | None  # nearest enclosing top-level function/class name, or None at module level


@dataclass(frozen=True)
class FileExtraction:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)


@dataclass(frozen=True)
class DependencyEdge:
    source_path: str
    target_path: str | None  # None => unresolved/external
    external_module: str | None  # raw specifier when target_path is None, else None
    type: str = "imports"


@dataclass(frozen=True)
class CallEdge:
    source_path: str
    source_symbol: str | None  # None = a module-level call, not inside any top-level function/class
    target_path: str | None  # None = unresolved
    target_symbol: str | None  # None = unresolved
    callee_name: str  # raw call-site identifier, kept even when unresolved (UI: "calls helper()")
    type: str = "calls"
