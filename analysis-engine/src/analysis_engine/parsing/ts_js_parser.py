from pathlib import Path

import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

_JS_PARSER = Parser(Language(tsjavascript.language()))
_TS_PARSER = Parser(Language(tstypescript.language_typescript()))
_TSX_PARSER = Parser(Language(tstypescript.language_tsx()))


def parser_for(path: Path) -> Parser:
    suffix = path.suffix.lower()
    if suffix == ".tsx":
        return _TSX_PARSER
    if suffix == ".ts":
        return _TS_PARSER
    return _JS_PARSER  # .js/.jsx/.mjs/.cjs -- the JS grammar also covers JSX


def parse_ok(source: bytes, path: Path) -> bool:
    """Day 1 only checks whether tree-sitter's CST contains an ERROR node.

    tree-sitter is error-tolerant and always returns *a* tree, so "parse_ok"
    means "no ERROR node", not "parse succeeded/failed" in the ast.parse
    sense. The extraction module walks this same tree via queries to pull
    out symbols/imports -- no re-parsing needed.
    """
    tree = parser_for(path).parse(source)
    return not tree.root_node.has_error
