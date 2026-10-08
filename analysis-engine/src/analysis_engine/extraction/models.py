from dataclasses import dataclass, field

# Bump whenever extraction logic changes what gets produced for
# byte-identical source (new symbol kind, new call-site shape, etc).
# Incremental analysis's content-hash cache (see pipeline.py's
# _build_file_summary) also checks this: a hash match from a prior
# EXTRACTOR_VERSION is NOT reused, so upgrading the engine doesn't silently
# keep serving stale extraction results for already-analyzed repositories.
EXTRACTOR_VERSION = 2


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str  # "function" | "class" | "variable" | "interface" | "type_alias" | "method"
    line_start: int
    line_end: int
    # Enclosing class name for a "method" symbol, None for everything else.
    # One level of nesting only (class -> method) -- deliberately not a full
    # qualified-name chain; see python_extractor.py/ts_js_extractor.py.
    parent: str | None = None


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
    # True for `self.foo()` (Python) / `this.foo()` (TS/JS) -- callee_name
    # can then ONLY be a method of `containing_symbol` (a class), never a
    # free function, so resolution must not fall back to a same-named
    # top-level function/class.
    is_method_call: bool = False


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
    # Enclosing class name when target_symbol is a "method" resolved via
    # self/this -- disambiguates same-named methods on different classes in
    # the same file (e.g. two classes both defining __init__) when looking
    # up the method's row id at persistence time. None for every other edge.
    target_parent: str | None = None
