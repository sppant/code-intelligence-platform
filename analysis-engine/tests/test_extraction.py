from pathlib import Path

from analysis_engine.extraction import python_extractor, ts_js_extractor
from analysis_engine.extraction.models import DependencyEdge, Import
from analysis_engine.extraction.resolution import resolve_relationships


# --- Python extractor ---


def test_python_extractor_finds_top_level_function_and_class():
    source = "def foo():\n    pass\n\n\nclass Bar:\n    def method(self):\n        pass\n"
    result = python_extractor.extract(source)
    kinds_by_name = {s.name: s.kind for s in result.symbols}
    assert kinds_by_name == {"foo": "function", "Bar": "class", "method": "method"}


def test_python_extractor_extracts_methods_with_parent_but_not_nested_functions():
    source = (
        "class Bar:\n"
        "    def method_one(self):\n"
        "        def inner():\n"
        "            pass\n"
        "        return inner\n"
        "    async def method_two(self):\n"
        "        pass\n"
    )
    result = python_extractor.extract(source)
    methods = [s for s in result.symbols if s.kind == "method"]
    assert {s.name for s in methods} == {"method_one", "method_two"}
    assert all(s.parent == "Bar" for s in methods)
    # one level of nesting only -- the method's own nested function isn't extracted
    assert "inner" not in {s.name for s in result.symbols}


def test_python_extractor_captures_self_method_calls_separately_from_plain_calls():
    source = (
        "class Bar:\n"
        "    def a(self):\n"
        "        self.b()\n"
        "        plain()\n"
        "    def b(self):\n"
        "        pass\n"
    )
    result = python_extractor.extract(source)
    self_call = next(c for c in result.calls if c.callee_name == "b")
    plain_call = next(c for c in result.calls if c.callee_name == "plain")
    assert self_call.is_method_call is True
    assert self_call.containing_symbol == "Bar"
    assert plain_call.is_method_call is False
    assert plain_call.containing_symbol == "Bar"


def test_python_extractor_finds_top_level_variables_only():
    source = "x = 1\n\n\ndef f():\n    y = 2\n    return y\n"
    result = python_extractor.extract(source)
    names = {s.name for s in result.symbols if s.kind == "variable"}
    assert names == {"x"}


def test_python_extractor_absolute_and_relative_imports():
    source = "import os\nfrom foo.bar import baz\nfrom . import sibling\nfrom .. import other\n"
    result = python_extractor.extract(source)
    assert result.imports[0].module == "os" and result.imports[0].level == 0
    assert result.imports[1].module == "foo.bar" and result.imports[1].level == 0
    assert result.imports[2].module == "" and result.imports[2].level == 1
    assert result.imports[3].module == "" and result.imports[3].level == 2


def test_python_extractor_import_bindings_for_call_resolution():
    source = (
        "import os\n"
        "from foo.bar import baz\n"
        "from foo.bar import qux as aliased\n"
        "from foo.bar import *\n"
    )
    result = python_extractor.extract(source)

    whole_module_import = result.imports[0]
    assert whole_module_import.local_name is None and whole_module_import.imported_name is None

    plain = next(i for i in result.imports if i.line == 2)
    assert plain.local_name == "baz" and plain.imported_name == "baz"

    aliased = next(i for i in result.imports if i.line == 3)
    assert aliased.local_name == "aliased" and aliased.imported_name == "qux"

    star = next(i for i in result.imports if i.line == 4)
    assert star.is_star is True and star.local_name is None


def test_python_extractor_multi_name_from_import_emits_one_row_per_name():
    source = "from foo import a, b as c\n"
    result = python_extractor.extract(source)
    assert len(result.imports) == 2
    assert {(i.local_name, i.imported_name) for i in result.imports} == {("a", "a"), ("c", "b")}


def test_python_extractor_collects_call_sites_with_containing_symbol():
    source = (
        "helper_at_module_level()\n"
        "def foo():\n"
        "    bar()\n"
        "class Baz:\n"
        "    def method(self):\n"
        "        qux()\n"
    )
    result = python_extractor.extract(source)
    by_name = {c.callee_name: c.containing_symbol for c in result.calls}
    assert by_name["helper_at_module_level"] is None
    assert by_name["bar"] == "foo"
    assert by_name["qux"] == "Baz"  # attributed to the enclosing top-level class, not the nested method


def test_python_extractor_excludes_attribute_calls():
    source = "obj.method()\n"
    result = python_extractor.extract(source)
    assert result.calls == []


# --- TS/JS extractor ---


def test_ts_js_extractor_finds_top_level_function_and_class():
    source = b"function foo() {}\nexport class Bar {}\nfunction outer() { function inner() {} }\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    kinds_by_name = {s.name: s.kind for s in result.symbols}
    assert kinds_by_name == {"foo": "function", "Bar": "class", "outer": "function"}
    assert "inner" not in kinds_by_name


def test_ts_js_extractor_handles_typescript_class_name_node_type():
    source = b"class Foo {}\ninterface Bar {}\ntype Baz = string;\n"
    result = ts_js_extractor.extract(source, Path("app.ts"))
    kinds_by_name = {s.name: s.kind for s in result.symbols}
    assert kinds_by_name == {"Foo": "class", "Bar": "interface", "Baz": "type_alias"}


def test_ts_js_extractor_ignores_interface_in_plain_js():
    # .d.ts-style syntax wouldn't parse as valid JS anyway; just confirm a
    # plain .js file never runs the TS-only queries.
    source = b"class Foo {}\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert [s.kind for s in result.symbols] == ["class"]


def test_ts_js_extractor_imports_and_export_from():
    source = b"import foo from './foo';\nexport { x } from './bar';\nimport pkg from 'some-package';\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    modules = {imp.module for imp in result.imports}
    assert modules == {"./foo", "./bar", "some-package"}


def test_ts_js_extractor_require_produces_import_edges():
    source = (
        b"const foo = require('./foo');\n"
        b"require('./sideeffect');\n"
        b"module.exports = require('./passthrough');\n"
        b"const pkg = require('some-package');\n"
    )
    result = ts_js_extractor.extract(source, Path("app.js"))
    modules = {imp.module for imp in result.imports}
    assert modules == {"./foo", "./sideeffect", "./passthrough", "some-package"}


def test_ts_js_extractor_require_destructured_bindings_for_call_resolution():
    source = b"const { a, b: bRenamed } = require('./bar');\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    bindings = {(i.local_name, i.imported_name) for i in result.imports}
    assert bindings == {("a", "a"), ("bRenamed", "b")}


def test_ts_js_extractor_require_simple_assignment_has_no_bindings():
    # `const foo = require('./foo')` binds the WHOLE module object to foo,
    # only ever used via foo.member -- unresolvable, like a default import.
    source = b"const foo = require('./foo');\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert result.imports[0].local_name is None


def test_ts_js_extractor_require_inside_a_function_is_not_extracted():
    # top-level only, same policy as ES imports.
    source = b"function f() {\n  const x = require('./x');\n  return x;\n}\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert result.imports == []


def test_ts_js_extractor_named_import_bindings_for_call_resolution():
    source = b"import { foo } from './a';\nimport { bar as baz } from './b';\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    plain = next(i for i in result.imports if i.module == "./a")
    assert plain.local_name == "foo" and plain.imported_name == "foo"
    aliased = next(i for i in result.imports if i.module == "./b")
    assert aliased.local_name == "baz" and aliased.imported_name == "bar"


def test_ts_js_extractor_default_and_namespace_imports_are_unresolvable():
    source = b"import def1 from './a';\nimport * as ns from './b';\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert all(i.local_name is None for i in result.imports)


def test_ts_js_extractor_export_from_never_contributes_call_bindings():
    source = b"export { x } from './bar';\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert result.imports[0].local_name is None


def test_ts_js_extractor_collects_call_sites_with_containing_symbol():
    source = (
        b"helperAtModuleLevel();\n"
        b"function foo() { bar(); }\n"
        b"class Baz { method() { qux(); } }\n"
        b"function outer() { function inner() { nested(); } }\n"
    )
    result = ts_js_extractor.extract(source, Path("app.js"))
    by_name = {c.callee_name: c.containing_symbol for c in result.calls}
    assert by_name["helperAtModuleLevel"] is None
    assert by_name["bar"] == "foo"
    assert by_name["qux"] == "Baz"
    assert by_name["nested"] == "outer"


def test_ts_js_extractor_excludes_attribute_calls():
    source = b"obj.method();\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert result.calls == []


def test_ts_js_extractor_extracts_methods_with_parent_including_static():
    source = b"class Foo {\n  bar() {}\n  static baz() {}\n}\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    methods = [s for s in result.symbols if s.kind == "method"]
    assert {s.name for s in methods} == {"bar", "baz"}
    assert all(s.parent == "Foo" for s in methods)


def test_ts_js_extractor_does_not_extract_methods_of_a_nested_class():
    # the owning class must itself be top-level -- a class defined inside a
    # function body isn't, so its methods aren't extracted either.
    source = b"function outer() {\n  class Inner {\n    method() {}\n  }\n  return Inner;\n}\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    assert [s.kind for s in result.symbols if s.kind == "method"] == []


def test_ts_js_extractor_captures_this_method_calls_separately_from_plain_calls():
    source = b"class Foo {\n  a() { this.b(); plain(); }\n  b() {}\n}\n"
    result = ts_js_extractor.extract(source, Path("app.js"))
    this_call = next(c for c in result.calls if c.callee_name == "b")
    plain_call = next(c for c in result.calls if c.callee_name == "plain")
    assert this_call.is_method_call is True
    assert this_call.containing_symbol == "Foo"
    assert plain_call.is_method_call is False


# --- resolution ---


def test_resolve_python_absolute_and_relative():
    files = [
        ("pkg/a.py", "python", [Import("pkg.b", 0, 1)]),
        ("pkg/b.py", "python", []),
        ("pkg/sub/c.py", "python", [Import("", 1, 1)]),  # from . import x -> pkg/sub/__init__.py
        ("pkg/sub/__init__.py", "python", []),
        ("pkg/d.py", "python", [Import("", 2, 1)]),  # from .. import x (level=2, no module) -> pkg's own init
    ]
    edges = resolve_relationships(files)
    by_source = {(e.source_path, e.target_path) for e in edges}
    assert ("pkg/a.py", "pkg/b.py") in by_source
    assert ("pkg/sub/c.py", "pkg/sub/__init__.py") in by_source


def test_resolve_python_unresolved_import_is_external():
    files = [("pkg/a.py", "python", [Import("requests", 0, 1)])]
    edges = resolve_relationships(files)
    assert edges == [DependencyEdge("pkg/a.py", None, "requests", "imports")]


def test_resolve_python_absolute_import_falls_back_to_src_layout():
    # `import mypkg.foo` with no literal "src" in the import itself, but
    # the package physically lives under src/ (editable/built install).
    files = [
        ("src/mypkg/__init__.py", "python", []),
        ("src/mypkg/foo.py", "python", []),
        ("main.py", "python", [Import("mypkg.foo", 0, 1)]),
    ]
    edges = resolve_relationships(files)
    by_source = {(e.source_path, e.target_path) for e in edges}
    assert ("main.py", "src/mypkg/foo.py") in by_source


def test_resolve_python_prefers_root_relative_over_src_layout_when_both_exist():
    files = [
        ("mypkg/foo.py", "python", []),
        ("src/mypkg/foo.py", "python", []),
        ("main.py", "python", [Import("mypkg.foo", 0, 1)]),
    ]
    edges = resolve_relationships(files)
    by_source = {(e.source_path, e.target_path) for e in edges}
    assert ("main.py", "mypkg/foo.py") in by_source


def test_resolve_ts_js_relative_with_index_fallback():
    files = [
        ("src/App.tsx", "typescript", [Import("./utils", 0, 1), Import("./Button", 0, 2)]),
        ("src/utils/index.ts", "typescript", []),
        ("src/Button.tsx", "typescript", []),
    ]
    edges = resolve_relationships(files)
    by_source = {(e.source_path, e.target_path) for e in edges}
    assert ("src/App.tsx", "src/utils/index.ts") in by_source
    assert ("src/App.tsx", "src/Button.tsx") in by_source


def test_resolve_ts_js_bare_specifier_is_external():
    files = [("src/App.tsx", "typescript", [Import("react", 0, 1)])]
    edges = resolve_relationships(files)
    assert len(edges) == 1
    assert edges[0].target_path is None
    assert edges[0].external_module == "react"


def test_resolve_relationships_deduplicates_edges():
    files = [
        ("pkg/a.py", "python", [Import("pkg.b", 0, 1), Import("pkg.b", 0, 2)]),
        ("pkg/b.py", "python", []),
    ]
    edges = resolve_relationships(files)
    assert len(edges) == 1
