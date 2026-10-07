from pathlib import Path

from analysis_engine.detection.languages import detect_languages


def test_detect_languages_counts_by_extension(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hi')\n")
    (tmp_path / "app.ts").write_text("const x: number = 1;\n")
    (tmp_path / "index.js").write_text("console.log('hi');\n")
    (tmp_path / "README.md").write_text("# hi\n")

    counts = detect_languages(tmp_path)

    assert counts == {"python": 1, "typescript": 1, "javascript": 1}


def test_detect_languages_ignores_vendored_directories(tmp_path: Path):
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    (nested / "index.js").write_text("module.exports = {};\n")
    (tmp_path / "main.py").write_text("print('hi')\n")

    counts = detect_languages(tmp_path)

    assert counts == {"python": 1}
