import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from analysis_engine.exceptions import (
    CloneFailedError,
    CloneTimeoutError,
    InvalidRepositoryUrlError,
    RepositoryTooLargeError,
)

_GITHUB_HOSTS = {"github.com", "www.github.com"}
_PATH_RE = re.compile(r"^/(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    name: str
    clone_url: str


def validate_github_url(raw_url: str) -> RepositoryRef:
    """Validate that `raw_url` points at a public GitHub repository.

    Rejects anything that isn't exactly `https://github.com/<owner>/<name>`
    (optionally with a trailing slash or `.git`) and reconstructs a canonical
    clone URL rather than ever passing the raw user string to a shell.
    """
    from urllib.parse import urlparse

    parsed = urlparse(raw_url.strip())

    if parsed.scheme != "https":
        raise InvalidRepositoryUrlError("Repository URL must use https://")

    if parsed.netloc.lower() not in _GITHUB_HOSTS:
        raise InvalidRepositoryUrlError("Only github.com repository URLs are supported")

    match = _PATH_RE.match(parsed.path)
    if not match:
        raise InvalidRepositoryUrlError("URL must look like https://github.com/<owner>/<repo>")

    owner, name = match.group("owner"), match.group("name")
    return RepositoryRef(owner=owner, name=name, clone_url=f"https://github.com/{owner}/{name}.git")


def clone_repository(ref: RepositoryRef, dest: Path, timeout_seconds: int) -> None:
    """Shallow-clone `ref` into `dest` with a hard timeout.

    Uses an explicit argument list (never `shell=True` / string interpolation)
    so the clone URL -- already validated by `validate_github_url` -- cannot
    be interpreted by a shell.
    """
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--", ref.clone_url, str(dest)],
            capture_output=True,
            timeout=timeout_seconds,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise CloneTimeoutError(f"Cloning {ref.clone_url} exceeded {timeout_seconds}s") from exc

    if result.returncode != 0:
        raise CloneFailedError(f"git clone failed for {ref.clone_url}: {_clean_clone_stderr(result.stderr)}")


def _clean_clone_stderr(stderr: str) -> str:
    """Drop git's own "Cloning into '<local tmp path>'..." progress line --
    it's not an error, just noise that also happens to echo the server's
    local scratch-directory path back into a message that ends up in the
    GraphQL-exposed job.error_message. The actual reason (e.g. "remote:
    Repository not found.") is always on the lines after it.
    """
    lines = [line for line in stderr.strip().splitlines() if not line.startswith("Cloning into ")]
    return " ".join(lines).strip() or stderr.strip()


def get_commit_sha(workspace: Path) -> str | None:
    """Best-effort `git rev-parse HEAD` for a freshly-cloned workspace.

    Purely informational (displayed in the UI, used by incremental analysis
    only as a nice-to-show value, never as the diffing mechanism itself --
    see pipeline.py's content-hash-based previous_files) -- returns None on
    any failure rather than raising, since a repository/clone that already
    succeeded shouldn't fail the whole analysis just because this couldn't
    be determined.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            capture_output=True,
            timeout=10,
            text=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def enforce_size_cap(path: Path, max_size_mb: int) -> None:
    """Walk `path` and abort if its total size exceeds `max_size_mb`.

    Called immediately after a clone, before any parsing touches the files.
    """
    max_bytes = max_size_mb * 1024 * 1024
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            total += file_path.stat().st_size
            if total > max_bytes:
                raise RepositoryTooLargeError(
                    f"Repository exceeds the {max_size_mb}MB size cap"
                )
