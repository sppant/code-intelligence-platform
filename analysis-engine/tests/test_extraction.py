from pathlib import Path

from analysis_engine.extraction import python_extractor, ts_js_extractor
from analysis_engine.extraction.models import DependencyEdge, Import
from analysis_engine.extraction.resolution import resolve_relationships


# --- Python extractor ---


def test_python_extractor_finds_top_level_function_and_class():
    source = "def foo():\n    pass\n\n\nclass Bar:\n    def method(self):\n        pass\n"
    result = python_extractor.extract(source)
    kinds_by_name = {s.name: s.kind for s in result.symbols}
    assert kinds_by_name == {"foo": "function", "Bar": "class"}
    # the nested method must NOT appear as a top-level symbol
    assert "method" not in kinds_by_name


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
