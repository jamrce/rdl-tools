"""Shared fixtures. The expensive ones are session-scoped: one `uv build`, one venv per run."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def built_dists(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """A real `uv build`, the same command `publish.yml` runs, so these tests see what PyPI would."""
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH — see CONTRIBUTING.md")
    outdir = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        ["uv", "build", "--out-dir", str(outdir), str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"uv build failed:\n{result.stdout}\n{result.stderr}")
    # uv drops a `.gitignore` beside the artefacts; only the distributions themselves are wanted.
    return sorted(p for p in outdir.iterdir() if p.name.endswith((".whl", ".tar.gz")))


@pytest.fixture(scope="session")
def wheel(built_dists: list[Path]) -> Path:
    return next(p for p in built_dists if p.suffix == ".whl")
