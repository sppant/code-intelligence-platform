from pathlib import Path

from analysis_engine.pipeline import analyze_workspace


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_file_over_size_cap_is_skipped_not_parsed(tmp_path: Path):
    """A single file past max_file_size_mb must not be handed to the
    parser, independent of enforce_size_cap's total-repo cap -- it should
    be recorded with parse_ok=False and no extracted symbols, not crash or
    silently get parsed anyway.
    """
    _write(tmp_path, "normal.py", "def foo():\n    pass\n")
    # Padded with a huge comment rather than huge code -- what matters here
    # is the file's byte size tripping the guard, not whether the content
    # would otherwise parse validly.
    _write(tmp_path, "huge.py", "# " + ("x" * 2_000_000) + "\ndef bar():\n    pass\n")

    result = analyze_workspace(tmp_path, max_file_size_mb=1)

    by_path = {f.path: f for f in result.files}
    assert by_path["normal.py"].parse_ok is True
    assert [s.name for s in by_path["normal.py"].symbols] == ["foo"]

    huge = by_path["huge.py"]
    assert huge.parse_ok is False
    assert huge.symbols == []
    assert huge.imports == []
    assert huge.calls == []
    # Still recorded (path, language, size, hash) for incremental caching
    # and the UI's file listing -- only parsing itself is skipped.
    assert huge.language == "python"
    assert huge.size_bytes is not None and huge.size_bytes > 1024 * 1024
    assert huge.content_hash is not None


def test_file_under_size_cap_is_parsed_normally(tmp_path: Path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")

    result = analyze_workspace(tmp_path, max_file_size_mb=1)

    [file_summary] = result.files
    assert file_summary.parse_ok is True
    assert [s.name for s in file_summary.symbols] == ["foo"]
