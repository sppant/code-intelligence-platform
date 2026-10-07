from collections.abc import Iterable
from dataclasses import dataclass

from analysis_engine.graph.cycles import find_cycles
from analysis_engine.graph.metrics import LARGE_FILE_LINE_THRESHOLD, fan_in_out, isolated_files, large_files


@dataclass(frozen=True)
class FileFanInOut:
    path: str
    fan_in: int
    fan_out: int


@dataclass(frozen=True)
class ArchitectureInsights:
    cycles: list[list[str]]
    fan_in_out: list[FileFanInOut]
    large_files: list[str]
    isolated_files: list[str]


def compute_architecture_insights(
    files: Iterable[tuple[str, int]],
    edges: Iterable[tuple[str, str]],
    large_file_threshold: int = LARGE_FILE_LINE_THRESHOLD,
) -> ArchitectureInsights:
    """`files` is (path, line_count) pairs; `edges` is (source, target)
    pairs -- already filtered to internal (both ends real repo files)
    edges by the caller, same convention as the rest of this package.

    NOTE on scope: "architectural boundary violations" from the original
    spec's wishlist is NOT attempted here -- it requires a concept of
    user-defined architectural layers this project has no notion of.
    Documented as a non-goal, not an oversight.
    """
    file_list = list(files)  # materialized: both the path extraction below
    # and large_files() further down each need to iterate this separately.
    paths = [path for path, _line_count in file_list]
    edge_list = list(edges)

    cycles = find_cycles(paths, edge_list)

    fan_in_out_counts = fan_in_out(paths, edge_list)
    fan_in_out_list = [FileFanInOut(path, *fan_in_out_counts[path]) for path in paths]
    fan_in_out_list.sort(key=lambda f: (f.fan_in + f.fan_out), reverse=True)

    return ArchitectureInsights(
        cycles=cycles,
        fan_in_out=fan_in_out_list,
        large_files=large_files(file_list, threshold=large_file_threshold),
        isolated_files=isolated_files(paths, edge_list),
    )
