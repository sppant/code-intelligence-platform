import pytest

from analysis_engine.exceptions import InvalidRepositoryUrlError
from analysis_engine.ingestion.clone import validate_github_url


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
