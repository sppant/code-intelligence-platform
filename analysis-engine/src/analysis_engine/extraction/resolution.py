import posixpath

from analysis_engine.extraction.models import DependencyEdge, Import

_TS_JS_CANDIDATE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")
_TS_JS_INDEX_CANDIDATES = tuple(f"index{suffix}" for suffix in _TS_JS_CANDIDATE_SUFFIXES)


def _resolve_python_import(source_path: str, imp: Import, known_paths: set[str]) -> str | None:
    """All path math here is lexical (posixpath.normpath on strings) -- it
    never touches the real filesystem, so this stays a pure, independently
    testable function over the already-collected set of repo paths.
    """
    source_dir = posixpath.dirname(source_path)

    if imp.level == 0:
        if not imp.module:
            return None  # defensive; absolute imports always carry a module name
        base = imp.module.replace(".", "/")
        candidates = (f"{base}.py", posixpath.join(base, "__init__.py"))
    else:
        # level=1 -> the importing file's own directory; each extra level
        # goes up one more parent.
        base = source_dir
        for _ in range(imp.level - 1):
            base = posixpath.dirname(base)
        if imp.module:
            base = posixpath.join(base, imp.module.replace(".", "/"))
            candidates = (f"{base}.py", posixpath.join(base, "__init__.py"))
        else:
            # `from . import x` / `from .. import x` -- the target is that
            # directory's own package, never a same-named sibling file.
            candidates = (posixpath.join(base, "__init__.py"),)

    for candidate in candidates:
        normalized = posixpath.normpath(candidate)
        if normalized in known_paths:
            return normalized
    return None


def _resolve_ts_js_import(source_path: str, imp: Import, known_paths: set[str]) -> str | None:
    if not (imp.module.startswith("./") or imp.module.startswith("../")):
        return None  # bare specifier: always external for Day 2

    source_dir = posixpath.dirname(source_path)
    target = posixpath.normpath(posixpath.join(source_dir, imp.module))

    if target in known_paths:
        return target
    for suffix in _TS_JS_CANDIDATE_SUFFIXES:
        candidate = f"{target}{suffix}"
        if candidate in known_paths:
            return candidate
    for index_name in _TS_JS_INDEX_CANDIDATES:
        candidate = posixpath.join(target, index_name)
        if candidate in known_paths:
            return candidate
    return None


def resolve_relationships(
    files_with_imports: list[tuple[str, str | None, list[Import]]],
) -> list[DependencyEdge]:
    """Resolve each file's imports against the repository's own file set,
    producing a deduplicated module-level dependency graph.

    `files_with_imports` is a list of (path, language, imports) -- language
    picks the resolution strategy; imports with no match (external package,
    bare specifier, asset, path outside the repo) become an edge with
    target_path=None and external_module set.
    """
    known_paths = {path for path, _language, _imports in files_with_imports}
    edges: set[DependencyEdge] = set()

    for source_path, language, imports in files_with_imports:
        for imp in imports:
            if language == "python":
                target = _resolve_python_import(source_path, imp, known_paths)
            else:
                target = _resolve_ts_js_import(source_path, imp, known_paths)

            if target is not None:
                edges.add(DependencyEdge(source_path, target, None, "imports"))
            else:
                edges.add(DependencyEdge(source_path, None, imp.module, "imports"))

    return sorted(edges, key=lambda e: (e.source_path, e.target_path or "", e.external_module or ""))
