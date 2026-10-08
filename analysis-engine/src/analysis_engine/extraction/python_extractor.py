import ast

from analysis_engine.extraction.models import CallSite, FileExtraction, Import, Symbol


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
        # One level of nesting only: methods defined directly in the class
        # body. A method's own nested functions are not extracted, matching
        # this visitor's deliberate no-recursion-past-top-level design.
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.symbols.append(
                    Symbol(member.name, "method", member.lineno, member.end_lineno or member.lineno, parent=node.name)
                )

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
        # `import foo.bar [as baz]` -- the bound name is only ever used via
        # attribute access (foo.bar.something()), which call resolution
        # deliberately doesn't attempt (no attribute-call resolution), so
        # local_name/imported_name are left unset here on purpose.
        for alias in node.names:
            self.imports.append(Import(module=alias.name, level=0, line=node.lineno))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if len(node.names) == 1 and node.names[0].name == "*":
            self.imports.append(Import(module=node.module or "", level=node.level, line=node.lineno, is_star=True))
            return
        for alias in node.names:
            self.imports.append(
                Import(
                    module=node.module or "",
                    level=node.level,
                    line=node.lineno,
                    local_name=alias.asname or alias.name,
                    imported_name=alias.name,
                )
            )


def _collect_calls(node: ast.AST, current_symbol: str | None, calls: list[CallSite]) -> None:
    """Walk the full tree (unlike _TopLevelVisitor, which deliberately never
    recurses) collecting every call to a plain name, plus the specific
    `self.foo()` shape of attribute call (general `obj.method()` stays
    excluded -- resolving an arbitrary attribute call needs type inference,
    out of scope; `self.foo()` doesn't, since `self`'s class is always the
    enclosing one). `current_symbol` tracks the nearest *top-level*
    function/class a call is nested inside: the `if current_symbol is None`
    guard means it's set once, on the module -> top-level-def transition,
    and never overwritten descending into nested defs/methods -- so a call
    inside a method is attributed to its enclosing top-level CLASS, not the
    specific method (methods aren't individually tracked as a "containing
    symbol", only as call resolution targets via Symbol.parent).
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            calls.append(CallSite(child.func.id, child.lineno, current_symbol))
        elif (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "self"
        ):
            calls.append(CallSite(child.func.attr, child.lineno, current_symbol, is_method_call=True))
        child_symbol = current_symbol
        if current_symbol is None and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            child_symbol = child.name
        _collect_calls(child, child_symbol, calls)


def extract(source: str) -> FileExtraction:
    """Extract top-level symbols, imports, and call sites from already-valid
    Python source (callers should only invoke this after confirming
    parse_ok).
    """
    tree = ast.parse(source)
    visitor = _TopLevelVisitor()
    for node in ast.iter_child_nodes(tree):
        visitor.visit(node)

    calls: list[CallSite] = []
    _collect_calls(tree, None, calls)

    return FileExtraction(symbols=visitor.symbols, imports=visitor.imports, calls=calls)
