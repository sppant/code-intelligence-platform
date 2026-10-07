from collections.abc import Iterable

# Between ESLint's `max-lines` default (300) and looser style norms (~500);
# named and overridable, matching this codebase's existing convention of
# named settings constants (e.g. Settings.stale_job_threshold_minutes).
LARGE_FILE_LINE_THRESHOLD = 400


def fan_in_out(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> dict[str, tuple[int, int]]:
    """Per-node (fan_in, fan_out) counts -- `edges` should already be
    filtered to internal (both ends are real repo files) edges by the
    caller; an edge whose endpoint isn't in `nodes` is silently ignored
    rather than inflating an unknown node's count.
    """
    node_set = set(nodes)
    fan_in = dict.fromkeys(node_set, 0)
    fan_out = dict.fromkeys(node_set, 0)
    for source, target in edges:
        if source in fan_out:
            fan_out[source] += 1
        if target in fan_in:
            fan_in[target] += 1
    return {node: (fan_in[node], fan_out[node]) for node in node_set}


def large_files(files: Iterable[tuple[str, int]], threshold: int = LARGE_FILE_LINE_THRESHOLD) -> list[str]:
    """Paths whose line_count exceeds `threshold`, largest first."""
    over = [(path, line_count) for path, line_count in files if line_count > threshold]
    over.sort(key=lambda item: item[1], reverse=True)
    return [path for path, _line_count in over]


def isolated_files(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str]:
    """Files with zero in-degree AND zero out-degree among internal edges.

    A file with only external imports (e.g. `import os`) still counts as
    isolated here -- "isolated" is about this repo's own internal
    architecture, not whether the file imports anything at all.
    """
    counts = fan_in_out(nodes, edges)
    return sorted(path for path, (fan_in, fan_out) in counts.items() if fan_in == 0 and fan_out == 0)
