from analysis_engine.extraction.call_resolution import resolve_calls
from analysis_engine.extraction.models import CallSite, Import, Symbol


def _fn(name: str) -> Symbol:
    return Symbol(name, "function", 1, 2)


def _method(name: str, parent: str) -> Symbol:
    return Symbol(name, "method", 1, 2, parent=parent)


def test_resolve_calls_same_file():
    files = [
        ("a.py", "python", [_fn("foo"), _fn("bar")], [], [CallSite("bar", 1, "foo")]),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_path == "a.py" and edge.source_symbol == "foo"
    assert edge.target_path == "a.py" and edge.target_symbol == "bar"
    assert edge.callee_name == "bar"


def test_resolve_calls_cross_file_via_plain_import():
    files = [
        ("a.py", "python", [_fn("foo")], [Import("b", 0, 1, local_name="helper", imported_name="helper")],
         [CallSite("helper", 2, "foo")]),
        ("b.py", "python", [_fn("helper")], [], []),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_path == "a.py" and edge.source_symbol == "foo"
    assert edge.target_path == "b.py" and edge.target_symbol == "helper"
    assert edge.callee_name == "helper"


def test_resolve_calls_cross_file_via_aliased_import():
    # `from b import helper as h` -- the call site uses "h", but the
    # resolved target symbol is "helper" (the ORIGINAL name in b.py).
    files = [
        ("a.py", "python", [], [Import("b", 0, 1, local_name="h", imported_name="helper")],
         [CallSite("h", 2, None)]),
        ("b.py", "python", [_fn("helper")], [], []),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.target_path == "b.py" and edge.target_symbol == "helper"
    assert edge.callee_name == "h"  # the raw call-site text, not the target's real name


def test_resolve_calls_unresolved_import_leaves_call_unresolved():
    files = [
        ("a.py", "python", [], [Import("requests", 0, 1, local_name="get", imported_name="get")],
         [CallSite("get", 2, None)]),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.target_path is None and edge.target_symbol is None
    assert edge.callee_name == "get"


def test_resolve_calls_star_import_is_never_used_for_resolution():
    files = [
        ("a.py", "python", [], [Import("b", 0, 1, is_star=True)], [CallSite("helper", 2, None)]),
        ("b.py", "python", [_fn("helper")], [], []),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    assert edges[0].target_path is None  # star imports never populate the bindings map


def test_resolve_calls_whole_module_import_has_no_bindings():
    # `import b` (no `from`) never resolves a direct call to a bound name --
    # it's only ever used via attribute access, out of scope.
    files = [
        ("a.py", "python", [], [Import("b", 0, 1)], [CallSite("b", 2, None)]),
        ("b.py", "python", [], [], []),
    ]
    edges = resolve_calls(files)
    assert edges[0].target_path is None


def test_resolve_calls_deduplicates_repeated_calls():
    files = [
        ("a.py", "python", [_fn("foo"), _fn("bar")], [],
         [CallSite("bar", 1, "foo"), CallSite("bar", 5, "foo")]),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1


def test_resolve_calls_target_symbol_must_be_function_or_class():
    # a same-named top-level *variable* is never a valid call target.
    files = [
        ("a.py", "python", [Symbol("thing", "variable", 1, 1)], [], [CallSite("thing", 2, None)]),
    ]
    edges = resolve_calls(files)
    assert edges[0].target_path is None


# --- method calls (self.foo() / this.foo()) ---


def test_resolve_method_call_same_class():
    files = [
        (
            "a.py",
            "python",
            [_method("a", "Foo"), _method("b", "Foo")],
            [],
            [CallSite("b", 1, "Foo", is_method_call=True)],
        ),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_path == "a.py" and edge.source_symbol == "Foo"
    assert edge.target_path == "a.py" and edge.target_symbol == "b"
    assert edge.target_parent == "Foo"


def test_resolve_method_call_unresolved_when_method_does_not_exist():
    files = [
        ("a.py", "python", [_method("a", "Foo")], [], [CallSite("missing", 1, "Foo", is_method_call=True)]),
    ]
    edges = resolve_calls(files)
    assert edges[0].target_path is None and edges[0].target_symbol is None


def test_resolve_method_call_disambiguates_same_named_methods_on_different_classes():
    # Two classes in the SAME file both define __init__ -- a self.__init__()
    # call inside Bar must resolve to Bar's __init__, not Foo's.
    files = [
        (
            "a.py",
            "python",
            [_method("__init__", "Foo"), _method("__init__", "Bar"), _method("reset", "Bar")],
            [],
            [CallSite("__init__", 1, "Bar", is_method_call=True)],
        ),
    ]
    edges = resolve_calls(files)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_symbol == "Bar" and edge.target_parent == "Bar"


def test_resolve_method_call_never_matches_an_unrelated_top_level_function():
    # self.foo() must NOT resolve against a same-named free function -- only
    # an actual method of the enclosing class is a valid target.
    files = [
        (
            "a.py",
            "python",
            [_fn("foo"), _method("a", "Foo")],
            [],
            [CallSite("foo", 1, "Foo", is_method_call=True)],
        ),
    ]
    edges = resolve_calls(files)
    assert edges[0].target_path is None and edges[0].target_symbol is None
