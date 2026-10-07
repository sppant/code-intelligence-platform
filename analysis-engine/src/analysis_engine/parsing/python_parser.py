import ast


def parse_ok(source: str) -> bool:
    """Day 1 only checks that the file is syntactically valid Python.

    Day 2 re-walks this same `ast.parse` tree with an `ast.NodeVisitor` to
    extract functions, classes, and imports -- no re-parsing needed.
    """
    try:
        ast.parse(source)
    except SyntaxError:
        return False
    return True
