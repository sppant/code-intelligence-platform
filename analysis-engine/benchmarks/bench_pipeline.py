"""Performance benchmark: full vs. incremental (zero-change) analysis time,
parse rate, across repos of increasing size.

Not pytest-discovered (needs real network clones and wall-clock timing) --
run manually:

    uv run --project analysis-engine python analysis-engine/benchmarks/bench_pipeline.py

Repos: small=pypa/sampleproject (~12 files), medium=psf/requests
(~130 files), large=django/django (~7000 files) -- chosen after checking
pallets/flask's actual size (236 files, only ~1.8x requests, not a
meaningful size step) and confirming django completes cleanly end to end
(see the commit that pinned tree-sitter to 0.23.x: analyzing django at this
scale is exactly what surfaced a real segfault in an earlier, unconstrained
tree-sitter version pin -- this script doubles as an implicit regression
check for that fix every time it's run).

Prints a markdown table; paste the real output into the README. Numbers
here are never fabricated -- this script is the thing that produces them.
"""

import time

from analysis_engine.pipeline import run_pipeline

REPOS = [
    ("pypa/sampleproject (small)", "https://github.com/pypa/sampleproject"),
    ("psf/requests (medium)", "https://github.com/psf/requests"),
    ("django/django (large)", "https://github.com/django/django"),
]

MAX_SIZE_MB = 2000
CLONE_TIMEOUT_SECONDS = 120


def _bench_one(label: str, url: str) -> dict:
    t0 = time.perf_counter()
    cold = run_pipeline(url, max_size_mb=MAX_SIZE_MB, clone_timeout_seconds=CLONE_TIMEOUT_SECONDS)
    full_seconds = time.perf_counter() - t0

    previous_files = {f.path: f for f in cold.files}

    t1 = time.perf_counter()
    warm = run_pipeline(
        url,
        max_size_mb=MAX_SIZE_MB,
        clone_timeout_seconds=CLONE_TIMEOUT_SECONDS,
        previous_files=previous_files,
    )
    incremental_seconds = time.perf_counter() - t1

    return {
        "label": label,
        "files": cold.total_files,
        "lines": cold.total_lines,
        "full_seconds": full_seconds,
        "incremental_seconds": incremental_seconds,
        "files_reused": warm.files_reused,
        "files_reprocessed": warm.files_reprocessed,
    }


def main() -> None:
    rows = []
    for label, url in REPOS:
        print(f"Benchmarking {label} ({url}) ...", flush=True)
        row = _bench_one(label, url)
        rows.append(row)
        print(
            f"  full={row['full_seconds']:.2f}s  incremental(0-change)={row['incremental_seconds']:.2f}s  "
            f"reused={row['files_reused']}/{row['files_reused'] + row['files_reprocessed']}",
            flush=True,
        )

    print("\n| Repo | Files | Lines | Full (s) | Incremental, 0-change (s) | Speedup | Files/sec (full) | Lines/sec (full) |")
    print("|---|---|---|---|---|---|---|---|")
    for row in rows:
        speedup = row["full_seconds"] / row["incremental_seconds"] if row["incremental_seconds"] > 0 else float("inf")
        files_per_sec = row["files"] / row["full_seconds"] if row["full_seconds"] > 0 else 0
        lines_per_sec = row["lines"] / row["full_seconds"] if row["full_seconds"] > 0 else 0
        print(
            f"| {row['label']} | {row['files']} | {row['lines']} | {row['full_seconds']:.2f} | "
            f"{row['incremental_seconds']:.2f} | {speedup:.1f}x | {files_per_sec:.0f} | {lines_per_sec:.0f} |"
        )


if __name__ == "__main__":
    main()
