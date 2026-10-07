import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def scratch_workspace(prefix: str = "cip-") -> Iterator[Path]:
    """Create an isolated, job-scoped temp directory and guarantee its cleanup.

    Never derive this path from user input -- it is always a fresh directory
    created by `tempfile.mkdtemp`, so nothing a cloned repository contains can
    influence where it lives.
    """
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
