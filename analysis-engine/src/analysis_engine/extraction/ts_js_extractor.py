from pathlib import Path

from tree_sitter import Language, Node, Query

from analysis_engine.extraction.models import CallSite, FileExtraction, Import, Symbol
from analysis_engine.parsing.ts_js_parser import parser_for

# Class name is `identifier` in the plain JS/JSX grammar but `type_identifier`
# in the TS/TSX grammar -- verified directly against the pinned tree-sitter
# grammar packages, not assumed.
_FUNCTION_QUERY = "(function_declaration name: (identifier) @name) @node"
_IMPORT_QUERY = "(import_statement source: (string (string_fragment) @module)) @node"
_EXPORT_FROM_QUERY = "(export_statement source: (string (string_fragment) @module)) @node"
_VARIABLE_QUERY = """
[
  (lexical_declaration (variable_declarator name: (identifier) @name)) @node
  (variable_declaration (variable_declarator name: (identifier) @name)) @node
]
"""
_CLASS_QUERY_BY_NAME_TYPE = {
    "identifier": "(class_declaration name: (identifier) @name) @node",
    "type_identifier": "(class_declaration name: (type_identifier) @name) @node",
}
_INTERFACE_QUERY = "(interface_declaration name: (type_identifier) @name) @node"
_TYPE_ALIAS_QUERY = "(type_alias_declaration name: (type_identifier) @name) @node"
# Excludes member_expression callees (obj.method()) by construction --
# method/attribute-call resolution is out of scope. Verified directly:
# `(call_expression function: (identifier) @callee)` only matches plain
# `foo()`-style calls, never `obj.method()`.
_CALL_QUERY = "(call_expression function: (identifier) @callee) @node"


class _CompiledQueries:
    """One set of compiled Query objects per grammar, built once (query
    compilation isn't free and there are only three grammars in play)."""

    def __init__(self, language: Language, class_name_type: str, include_ts_only: bool) -> None:
        self.function = Query(language, _FUNCTION_QUERY)
        self.variable = Query(language, _VARIABLE_QUERY)
        self.class_ = Query(language, _CLASS_QUERY_BY_NAME_TYPE[class_name_type])
        self.import_ = Query(language, _IMPORT_QUERY)
        self.export_from = Query(language, _EXPORT_FROM_QUERY)
        self.call = Query(language, _CALL_QUERY)
        self.interface = Query(language, _INTERFACE_QUERY) if include_ts_only else None
        self.type_alias = Query(language, _TYPE_ALIAS_QUERY) if include_ts_only else None


def _build_compiled(path: Path) -> _CompiledQueries:
    parser = parser_for(path)
    suffix = path.suffix.lower()
    is_ts = suffix in (".ts", ".tsx")
    class_name_type = "type_identifier" if is_ts else "identifier"
    return _CompiledQueries(parser.language, class_name_type, include_ts_only=is_ts)


_COMPILED_BY_SUFFIX: dict[str, _CompiledQueries] = {}


def _compiled_for(path: Path) -> _CompiledQueries:
    suffix = path.suffix.lower()
    key = suffix if suffix in (".ts", ".tsx") else ".js"  # .js/.jsx/.mjs/.cjs share the JS grammar
    if key not in _COMPILED_BY_SUFFIX:
        _COMPILED_BY_SUFFIX[key] = _build_compiled(path)
    return _COMPILED_BY_SUFFIX[key]


def _is_top_level(node: Node) -> bool:
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "program":
        return True
    return parent.type == "export_statement" and parent.parent is not None and parent.parent.type == "program"


def _matches(query: Query, root: Node) -> list[dict[str, list[Node]]]:
    # tree-sitter 0.23.x: Query.matches() directly (no separate QueryCursor
    # -- that's a 0.26+ API this pinned version predates). Verified directly
    # against the pinned package, not assumed: same (pattern_index, captures)
    # tuple shape either way.
    return [captures for _pattern_index, captures in query.matches(root)]


def _symbols_from(query: Query, root: Node, kind: str) -> list[Symbol]:
    symbols = []
    for captures in _matches(query, root):
        node = captures["node"][0]
        if not _is_top_level(node):
            continue
        name = captures["name"][0].text.decode("utf-8")
        symbols.append(Symbol(name, kind, node.start_point.row + 1, node.end_point.row + 1))
    return symbols


def _named_bindings(import_node: Node) -> list[tuple[str, str]]:
    """Return (local_name, imported_name) pairs bound by `import { ... }`
    clauses -- verified node shape: import_statement -> import_clause ->
    named_imports -> import_specifier, with fields "name" (always present)
    and "alias" (only when `as` is used).

    Default imports (`import foo from './x'` -- import_clause's direct
    child is a bare identifier, no named_imports wrapper) and namespace
    imports (`import * as ns from './x'` -- import_clause ->
    namespace_import) are structurally distinct from this and are walked
    past here without matching anything: deliberately unresolvable for call
    resolution (default-export name matching is unreliable without deeper
    export-binding analysis; namespace imports are only ever used via
    attribute access, out of scope regardless).
    """
    bindings = []
    for clause in import_node.children:
        if clause.type != "import_clause":
            continue
        for part in clause.children:
            if part.type != "named_imports":
                continue
            for specifier in part.children:
                if specifier.type != "import_specifier":
                    continue
                name_node = specifier.child_by_field_name("name")
                alias_node = specifier.child_by_field_name("alias")
                if name_node is None:
                    continue
                imported = name_node.text.decode("utf-8")
                local = alias_node.text.decode("utf-8") if alias_node else imported
                bindings.append((local, imported))
    return bindings


def _imports_from(query: Query, root: Node, *, with_bindings: bool) -> list[Import]:
    imports = []
    for captures in _matches(query, root):
        node = captures["node"][0]
        if not _is_top_level(node):
            continue
        module = captures["module"][0].text.decode("utf-8")
        line = node.start_point.row + 1

        # `export {x} from './y'` re-exports are edges only, never call
        # bindings -- bindings are only collected for real import_statements.
        bindings = _named_bindings(node) if (with_bindings and node.type == "import_statement") else []

        if bindings:
            for local_name, imported_name in bindings:
                imports.append(
                    Import(module=module, level=0, line=line, local_name=local_name, imported_name=imported_name)
                )
        else:
            imports.append(Import(module=module, level=0, line=line))
    return imports


def _containing_top_level_symbol(node: Node) -> str | None:
    """Walk up from a call site to the nearest enclosing top-level
    function/class declaration. Nested (non-top-level) functions/classes
    fail _is_top_level and are walked past, so this finds the outermost
    top-level ancestor regardless of nesting depth -- verified directly
    (a call inside `function outer(){ function inner(){ call() } }` walks
    past `inner`, whose parent is a statement_block, to `outer`, whose
    parent is `program`).
    """
    current = node.parent
    while current is not None:
        if current.type in ("function_declaration", "class_declaration") and _is_top_level(current):
            name_node = current.child_by_field_name("name")
            return name_node.text.decode("utf-8") if name_node else None
        current = current.parent
    return None


def _calls_from(query: Query, root: Node) -> list[CallSite]:
    calls = []
    for captures in _matches(query, root):
        node = captures["node"][0]
        callee = captures["callee"][0].text.decode("utf-8")
        calls.append(CallSite(callee, node.start_point.row + 1, _containing_top_level_symbol(node)))
    return calls


def extract(source: bytes, path: Path) -> FileExtraction:
    """Extract top-level symbols, imports, and call sites from already-valid
    TS/JS source (callers should only invoke this after confirming
    parse_ok).
    """
    tree = parser_for(path).parse(source)
    root = tree.root_node
    compiled = _compiled_for(path)

    symbols: list[Symbol] = []
    symbols += _symbols_from(compiled.function, root, "function")
    symbols += _symbols_from(compiled.class_, root, "class")
    symbols += _symbols_from(compiled.variable, root, "variable")
    if compiled.interface is not None:
        symbols += _symbols_from(compiled.interface, root, "interface")
    if compiled.type_alias is not None:
        symbols += _symbols_from(compiled.type_alias, root, "type_alias")

    imports: list[Import] = []
    imports += _imports_from(compiled.import_, root, with_bindings=True)
    # `export { x } from "./y"` / `export * from "./y"` is the same module
    # dependency edge as an import for our purposes (module-level graph).
    imports += _imports_from(compiled.export_from, root, with_bindings=False)

    calls = _calls_from(compiled.call, root)

    return FileExtraction(symbols=symbols, imports=imports, calls=calls)
