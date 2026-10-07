from pathlib import Path

from tree_sitter import Language, Node, Query, QueryCursor

from analysis_engine.extraction.models import FileExtraction, Import, Symbol
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


class _CompiledQueries:
    """One set of compiled Query objects per grammar, built once (query
    compilation isn't free and there are only three grammars in play)."""

    def __init__(self, language: Language, class_name_type: str, include_ts_only: bool) -> None:
        self.function = Query(language, _FUNCTION_QUERY)
        self.variable = Query(language, _VARIABLE_QUERY)
        self.class_ = Query(language, _CLASS_QUERY_BY_NAME_TYPE[class_name_type])
        self.import_ = Query(language, _IMPORT_QUERY)
        self.export_from = Query(language, _EXPORT_FROM_QUERY)
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
    return [captures for _pattern_index, captures in QueryCursor(query).matches(root)]


def _symbols_from(query: Query, root: Node, kind: str) -> list[Symbol]:
    symbols = []
    for captures in _matches(query, root):
        node = captures["node"][0]
        if not _is_top_level(node):
            continue
        name = captures["name"][0].text.decode("utf-8")
        symbols.append(Symbol(name, kind, node.start_point.row + 1, node.end_point.row + 1))
    return symbols


def _imports_from(query: Query, root: Node) -> list[Import]:
    imports = []
    for captures in _matches(query, root):
        node = captures["node"][0]
        if not _is_top_level(node):
            continue
        module = captures["module"][0].text.decode("utf-8")
        imports.append(Import(module=module, level=0, line=node.start_point.row + 1))
    return imports


def extract(source: bytes, path: Path) -> FileExtraction:
    """Extract top-level symbols and imports from already-valid TS/JS source
    (callers should only invoke this after confirming parse_ok).
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
    imports += _imports_from(compiled.import_, root)
    # `export { x } from "./y"` / `export * from "./y"` is the same module
    # dependency edge as an import for our purposes (module-level graph).
    imports += _imports_from(compiled.export_from, root)

    return FileExtraction(symbols=symbols, imports=imports)
