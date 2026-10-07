import re
from collections.abc import Iterable

_TEST_DIR_SEGMENTS = {"test", "tests", "__tests__"}
_TEST_FILENAME_PATTERNS = [
    re.compile(r"^test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r".*\.(test|spec)\.(ts|tsx|js|jsx)$"),
]


def is_test_file(path: str) -> bool:
    """A concrete, stated heuristic -- not exhaustive, but covers the
    overwhelmingly common conventions in both ecosystems."""
    parts = path.lower().split("/")
    if any(part in _TEST_DIR_SEGMENTS for part in parts[:-1]):
        return True
    filename = parts[-1]
    return any(pattern.match(filename) for pattern in _TEST_FILENAME_PATTERNS)


def affected_files(target_path: str, edges: Iterable[tuple[str, str]]) -> set[str]:
    """Every file that transitively depends on `target_path` via `edges`
    (source, target) pairs -- i.e. a reverse-BFS over "who imports this
    file, and who imports THEM". Excludes target_path itself.
    """
    reverse_adj: dict[str, list[str]] = {}
    for source, target in edges:
        reverse_adj.setdefault(target, []).append(source)

    visited: set[str] = set()
    queue = [target_path]
    while queue:
        current = queue.pop()
        for dependent in reverse_adj.get(current, []):
            if dependent not in visited and dependent != target_path:
                visited.add(dependent)
                queue.append(dependent)
    return visited


def compute_risk_indicators(
    *,
    fan_in: int,
    affected_files_count: int,
    affected_tests_count: int,
    direct_callers_count: int,
    symbol_kind: str,
    high_coupling_threshold: int = 10,
    wide_blast_radius_threshold: int = 20,
) -> list[str]:
    indicators = []
    if fan_in > high_coupling_threshold:
        indicators.append("High coupling")
    if affected_tests_count == 0:
        indicators.append("Missing test coverage")
    if affected_files_count > wide_blast_radius_threshold:
        indicators.append("Wide blast radius")
    if direct_callers_count == 0 and symbol_kind == "function":
        # A real false-positive risk: entry points, CLI commands, and
        # framework-invoked handlers (route handlers, event listeners,
        # pytest fixtures) are never "called" in the repo's own call graph
        # by construction -- flagged anyway since most functions aren't
        # entry points, but worth stating plainly rather than silently
        # over-trusting the signal.
        indicators.append("No direct callers found (may be an entry point or invoked via a framework)")
    return indicators
