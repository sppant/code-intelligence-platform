from pathlib import Path

from analysis_engine.pipeline import analyze_workspace


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_unchanged_file_is_reused_and_changed_file_is_reprocessed(tmp_path: Path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    _write(tmp_path, "b.py", "def bar():\n    pass\n")

    first = analyze_workspace(tmp_path)
    assert first.is_incremental is False
    assert first.files_reused == 0
    assert first.files_reprocessed == 2

    previous_files = {f.path: f for f in first.files}

    # Only b.py changes.
    _write(tmp_path, "b.py", "def bar():\n    pass\n\n\ndef baz():\n    pass\n")

    second = analyze_workspace(tmp_path, previous_files=previous_files)
    assert second.is_incremental is True
    assert second.files_reused == 1
    assert second.files_reprocessed == 1

    symbols_by_path = {f.path: [s.name for s in f.symbols] for f in second.files}
    assert symbols_by_path["a.py"] == ["foo"]  # reused verbatim
    assert symbols_by_path["b.py"] == ["bar", "baz"]  # reprocessed, new symbol present


def test_deleted_dependency_target_does_not_leave_dangling_edge(tmp_path: Path):
    _write(tmp_path, "a.py", "def helper():\n    pass\n")
    _write(tmp_path, "b.py", "from a import helper\nhelper()\n")

    first = analyze_workspace(tmp_path)
    edges_by_source = {e.source_path: e for e in first.dependency_edges}
    assert edges_by_source["b.py"].target_path == "a.py"  # sanity: resolved before deletion

    previous_files = {f.path: f for f in first.files}

    # a.py is deleted; b.py itself is untouched.
    (tmp_path / "a.py").unlink()

    second = analyze_workspace(tmp_path, previous_files=previous_files)
    assert second.files_reused == 1  # b.py's content is unchanged, so it WAS reused
    assert second.files_reprocessed == 0

    edges_by_source = {e.source_path: e for e in second.dependency_edges}
    assert edges_by_source["b.py"].target_path is None  # not a dangling reference to a.py
    assert edges_by_source["b.py"].external_module == "a"

    calls_by_source = {c.source_path: c for c in second.call_edges}
    assert calls_by_source["b.py"].target_path is None
    assert calls_by_source["b.py"].target_symbol is None


def test_reprocessing_a_changed_file_does_not_use_stale_cache(tmp_path: Path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    first = analyze_workspace(tmp_path)
    previous_files = {f.path: f for f in first.files}

    _write(tmp_path, "a.py", "def foo():\n    pass\n\n\ndef newly_added():\n    pass\n")
    second = analyze_workspace(tmp_path, previous_files=previous_files)

    assert second.files_reused == 0
    assert second.files_reprocessed == 1
    names = {s.name for f in second.files for s in f.symbols}
    assert names == {"foo", "newly_added"}


def test_no_previous_files_means_not_incremental(tmp_path: Path):
    _write(tmp_path, "a.py", "x = 1\n")
    result = analyze_workspace(tmp_path, previous_files=None)
    assert result.is_incremental is False
    assert result.files_reused == 0
    assert result.files_reprocessed == 1
