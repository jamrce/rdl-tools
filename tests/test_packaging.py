"""What has to be true of the distribution itself, not of any generator."""

from __future__ import annotations

import subprocess
import sys
import tomllib
import zipfile
from importlib import resources
from pathlib import Path

import pytest

import rdl_tools
from rdl_tools import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def project_metadata() -> dict:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


# metadata


def test_the_package_version_and_pyproject_agree():
    # publish.yml asserts the release tag against pyproject; this asserts the runtime constant
    # against the same value, so `rdl-tools --version` can never lie about what is installed.
    assert project_metadata()["project"]["version"] == __version__


def test_no_module_skeleton_is_shipped():
    # The skeleton belongs to rdl-module-template; a second copy here would drift.
    root = Path(str(resources.files("rdl_tools")))
    assert not (root / "template").exists()
    assert not (root / "website").exists()


def test_pypi_metadata_is_complete_enough_to_publish():
    project = project_metadata()["project"]
    assert project["readme"]
    assert project["requires-python"] == ">=3.13"
    assert project["urls"]["Homepage"]
    # PEP 639: an SPDX expression and the licence file, not a `License ::` classifier.
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE.md"]
    assert not [c for c in project["classifiers"] if c.startswith("License ::")]
    assert "Typing :: Typed" in project["classifiers"]


def test_the_package_declares_inline_types():
    assert resources.files(rdl_tools).joinpath("py.typed").is_file()


# built artefacts


# `built_dists` is a session fixture in conftest.py.


def test_the_wheel_carries_the_tool_and_no_skeleton(built_dists):
    wheel = next(p for p in built_dists if p.suffix == ".whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert "rdl_tools/py.typed" in names
    assert "rdl_tools/cli.py" in names
    assert not [n for n in names if n.startswith("rdl_tools/template/")]
    # A stray lockfile or web font means the skeleton has crept back in.
    assert not [n for n in names if n.endswith((".woff2", "package-lock.json"))]


def test_the_sdist_carries_the_tests_and_the_licence(built_dists):
    import tarfile

    sdist = next(p for p in built_dists if p.name.endswith(".tar.gz"))
    with tarfile.open(sdist) as archive:
        names = {n.split("/", 1)[1] for n in archive.getnames() if "/" in n}
    assert "LICENSE.md" in names
    assert "CHANGELOG.md" in names
    assert "tests/test_init.py" in names


def test_twine_accepts_both_artefacts(built_dists):
    pytest.importorskip("twine", reason="the `dev` extra is not installed")
    result = subprocess.run(
        [sys.executable, "-m", "twine", "check", *[str(p) for p in built_dists]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
