import subprocess
from pathlib import Path

import pytest

from analysis_engine.exceptions import InvalidRepositoryUrlError
from analysis_engine.ingestion.clone import get_commit_sha, validate_github_url


def test_validate_github_url_accepts_canonical_url():
    ref = validate_github_url("https://github.com/octocat/Hello-World")
    assert ref.owner == "octocat"
    assert ref.name == "Hello-World"
    assert ref.clone_url == "https://github.com/octocat/Hello-World.git"


def test_validate_github_url_accepts_trailing_slash_and_dot_git():
    ref = validate_github_url("https://github.com/octocat/Hello-World.git/")
    assert ref.owner == "octocat"
    assert ref.name == "Hello-World"


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://github.com/octocat/Hello-World",  # not https
        "https://notgithub.com/octocat/Hello-World",  # wrong host
        "https://github.com/octocat",  # missing repo name
        "https://github.com/octocat/../../etc/passwd",  # path traversal attempt
        "https://github.com/owner/name; rm -rf /",  # shell-injection attempt
    ],
)
def test_validate_github_url_rejects_invalid_urls(bad_url):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_github_url(bad_url)


def test_get_commit_sha_returns_head_sha_for_a_git_repo(tmp_path: Path):
    (tmp_path / "file.txt").write_text("hello\n")
    env_args = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
    subprocess.run(["git", *env_args, "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", *env_args, "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", *env_args, "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    sha = get_commit_sha(tmp_path)

    assert sha is not None
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_get_commit_sha_returns_none_when_not_a_git_repo(tmp_path: Path):
    assert get_commit_sha(tmp_path) is None
