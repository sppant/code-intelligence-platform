from analysis_engine.extraction.models import CallEdge, CallSite, Import, Symbol
from analysis_engine.extraction.resolution import resolve_import_target


def resolve_calls(
    files: list[tuple[str, str | None, list[Symbol], list[Import], list[CallSite]]],
) -> list[CallEdge]:
    """Resolve each file's call sites into a deduplicated call graph.

    `files` is a list of (path, language, symbols, imports, calls). Two
    kinds of call site are resolved independently:

    Plain calls (`foo()`), tried in order:
      1. a same-name top-level function/class defined in the SAME file;
      2. a same-name-bound import whose target file (via the already-
         verified Day 2 path resolution) defines that symbol under its
         ORIGINAL name (which can differ from the local/bound name on a
         Python `as` alias or a TS/JS `{x as y}` import).

    Method calls (`self.foo()` / `this.foo()`, `call.is_method_call=True`):
    resolved ONLY against methods of the enclosing class
    (`call.containing_symbol`) in the SAME file -- `self`/`this` can never
    refer to an imported class, so there's no cross-file case to try, and a
    same-named top-level FUNCTION must never match here (self.foo() cannot
    mean "the free function foo").

    Anything else is recorded unresolved (target_path/target_symbol=None)
    but still carries callee_name, so a caller can show "calls helper()"
    even when the target couldn't be determined. Variables/interfaces/type
    aliases are excluded from the plain-call lookup table -- only functions
    and classes are ever plain-call targets (no type inference, consistent
    with excluding general attribute calls entirely).
    """
    known_paths = {path for path, *_ in files}
    callables_by_file: dict[str, dict[str, Symbol]] = {
        path: {s.name: s for s in symbols if s.kind in ("function", "class")}
        for path, _language, symbols, _imports, _calls in files
    }
    # Keyed by (path, owning class name) so two classes in the same file
    # that both define e.g. __init__ don't collide.
    methods_by_file_and_class: dict[tuple[str, str], dict[str, Symbol]] = {}
    for path, _language, symbols, _imports, _calls in files:
        for s in symbols:
            if s.kind == "method" and s.parent:
                methods_by_file_and_class.setdefault((path, s.parent), {})[s.name] = s

    edges: set[CallEdge] = set()
    for path, language, _symbols, imports, calls in files:
        bindings: dict[str, Import] = {i.local_name: i for i in imports if i.local_name and not i.is_star}

        for call in calls:
            name = call.callee_name

            if call.is_method_call:
                owning_class = call.containing_symbol
                method = methods_by_file_and_class.get((path, owning_class or ""), {}).get(name) if owning_class else None
                if method:
                    edges.add(CallEdge(path, owning_class, path, name, name, target_parent=owning_class))
                else:
                    edges.add(CallEdge(path, owning_class, None, None, name))
                continue

            if name in callables_by_file.get(path, {}):
                edges.add(CallEdge(path, call.containing_symbol, path, name, name))
                continue

            imp = bindings.get(name)
            target = resolve_import_target(path, language, imp, known_paths) if imp else None
            target_symbol = imp.imported_name if (imp and target) else None

            if target and target_symbol and target_symbol in callables_by_file.get(target, {}):
                edges.add(CallEdge(path, call.containing_symbol, target, target_symbol, name))
            else:
                edges.add(CallEdge(path, call.containing_symbol, None, None, name))

    return sorted(edges, key=lambda e: (e.source_path, e.source_symbol or "", e.callee_name))
