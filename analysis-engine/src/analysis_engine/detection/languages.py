from collections.abc import Iterator
from pathlib import Path

# Extension -> language name. Broad enough to describe a repo's overall
# language mix; only "python", "javascript" and "typescript" get real parsing
# in Day 1 (see analysis_engine.parsing).
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}

# Manifest files that confirm a language/ecosystem even without counting
# every matching source extension.
MANIFEST_LANGUAGE_MAP: dict[str, str] = {
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "Gemfile": "ruby",
}

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def iter_source_files(root: Path) -> Iterator[Path]:
    """Yield every file under `root`, skipping ignored/VCS/dependency dirs."""
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def detect_language(path: Path) -> str | None:
    return EXTENSION_LANGUAGE_MAP.get(path.suffix.lower())


def detect_languages(root: Path) -> dict[str, int]:
    """Return a {language: file_count} map for the repository at `root`."""
    counts: dict[str, int] = {}
    for path in iter_source_files(root):
        language = detect_language(path) or MANIFEST_LANGUAGE_MAP.get(path.name)
        if language:
            counts[language] = counts.get(language, 0) + 1
    return counts
