import ast

from analysis_engine.extraction.models import FileExtraction, Import, Symbol


class _TopLevelVisitor(ast.NodeVisitor):
    """Visits only top-level statements: callers drive this by calling
    visit() on each child of the module directly (see extract(), below)
    rather than visit(tree), and none of the handlers here call
    generic_visit, so nested defs/methods are never reached.
    """

    def __init__(self) -> None:
        self.symbols: list[Symbol] = []
        self.imports: list[Import] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.symbols.append(Symbol(node.name, "function", node.lineno, node.end_lineno or node.lineno))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.symbols.append(Symbol(node.name, "function", node.lineno, node.end_lineno or node.lineno))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(Symbol(node.name, "class", node.lineno, node.end_lineno or node.lineno))

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.symbols.append(
                    Symbol(target.id, "variable", node.lineno, node.end_lineno or node.lineno)
                )

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.symbols.append(
                Symbol(node.target.id, "variable", node.lineno, node.end_lineno or node.lineno)
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(Import(module=alias.name, level=0, line=node.lineno))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(Import(module=node.module or "", level=node.level, line=node.lineno))


def extract(source: str) -> FileExtraction:
    """Extract top-level symbols and imports from already-valid Python
    source (callers should only invoke this after confirming parse_ok).
    """
    tree = ast.parse(source)
    visitor = _TopLevelVisitor()
    for node in ast.iter_child_nodes(tree):
        visitor.visit(node)
    return FileExtraction(symbols=visitor.symbols, imports=visitor.imports)
