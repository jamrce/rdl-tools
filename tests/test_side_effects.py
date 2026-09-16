"""The paths that shell out or reach the network, with the subprocess and the transport faked.

`bootstrap` runs `venv`, `pip` and `npm`; `fetch-fonts` downloads. What is asserted is the
argv each would have run, and the tree each would have written.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

from rdl_tools import bootstrap
from rdl_tools.cli import main
from rdl_tools.commands import fetch_fonts

# bootstrap


class RecordingRun:
    """Stands in for subprocess.run, recording argv and creating whatever the real tool would."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append([str(a) for a in argv])
        if "venv" in argv:
            target = Path(argv[-1])
            (target / "bin").mkdir(parents=True, exist_ok=True)
            (target / "bin" / "python").write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)


# What shutil.which would hand back on Windows, where npm is a .cmd and not on PATHEXT's radar.
RESOLVED_NPM = "/opt/fake/npm.cmd"


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> RecordingRun:
    runner = RecordingRun()
    monkeypatch.setattr(bootstrap.subprocess, "run", runner)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: RESOLVED_NPM if name == "npm" else None)
    return runner


def test_finish_setup_creates_a_venv_installs_both_dependency_sets_and_activates_ci(
    tmp_path: Path, recorded: RecordingRun
):
    (tmp_path / "github" / "workflows").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.1.0\n", encoding="utf-8")
    (tmp_path / "website").mkdir()

    notes = bootstrap.finish_setup(tmp_path)

    assert (tmp_path / ".github" / "workflows").is_dir()
    assert any("venv" in call for call in recorded.calls)
    assert any(call[-4:] == ["-m", "pip", "install", "-r"] or "pip" in call for call in recorded.calls)
    assert [RESOLVED_NPM, "install"] in recorded.calls
    assert any("Activated CI" in note for note in notes)
    assert any("Node dependencies" in note for note in notes)


def test_an_existing_venv_is_reused_rather_than_recreated(tmp_path: Path, recorded: RecordingRun):
    (tmp_path / ".venv").mkdir()
    bootstrap.create_venv(tmp_path)
    assert recorded.calls == []


def test_pip_install_is_skipped_without_a_requirements_file(tmp_path: Path, recorded: RecordingRun):
    bootstrap.pip_install(tmp_path, tmp_path / ".venv")
    assert recorded.calls == []


def test_pip_install_targets_pypi_unless_an_index_override_is_set(
    tmp_path: Path, recorded: RecordingRun, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.1.0\n", encoding="utf-8")
    monkeypatch.delenv("RDL_TOOLS_INDEX_URL", raising=False)
    bootstrap.pip_install(tmp_path, tmp_path / ".venv")
    assert "--index-url" not in recorded.calls[0]


def test_pip_install_honours_the_index_override_used_by_the_testpypi_rehearsal(
    tmp_path: Path, recorded: RecordingRun, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.1.0rc1\n", encoding="utf-8")
    monkeypatch.setenv("RDL_TOOLS_INDEX_URL", "https://test.pypi.org/simple/")
    bootstrap.pip_install(tmp_path, tmp_path / ".venv")
    call = recorded.calls[0]
    assert call[call.index("--index-url") + 1] == "https://test.pypi.org/simple/"
    # Dependencies must still resolve from real PyPI; TestPyPI does not carry rdflib or pyshacl.
    assert call[call.index("--extra-index-url") + 1] == "https://pypi.org/simple"


def test_a_cross_platform_node_modules_is_wiped_before_reinstalling(tmp_path: Path, recorded: RecordingRun):
    website = tmp_path / "website"
    bin_dir = website / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    # Whichever OS this runs on, plant the *other* one's shims.
    foreign = "docusaurus" if platform.system() == "Windows" else "docusaurus.cmd"
    (bin_dir / foreign).write_text("", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.1.0\n", encoding="utf-8")

    notes = bootstrap.finish_setup(tmp_path)

    assert not (website / "node_modules").exists() or not (website / "node_modules" / ".bin").exists()
    assert [RESOLVED_NPM, "install"] in recorded.calls
    assert any("mismatch detected" in note for note in notes)


def test_a_module_without_a_website_installs_no_node_dependencies(tmp_path: Path, recorded: RecordingRun):
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.1.0\n", encoding="utf-8")
    notes = bootstrap.finish_setup(tmp_path)
    assert not [c for c in recorded.calls if c[0] == RESOLVED_NPM]
    assert not any("Node dependencies" in note for note in notes)


def test_npm_that_is_not_on_path_is_named_rather_than_a_winerror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="npm is not on PATH"):
        bootstrap.npm_install(tmp_path)


def test_venv_python_path_is_platform_correct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Windows")
    assert bootstrap.venv_python(tmp_path).name == "python.exe"
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Linux")
    assert bootstrap.venv_python(tmp_path).parts[-2:] == ("bin", "python")


# fetch-fonts

CSS2_RESPONSE = """/* latin */
@font-face {
  font-family: 'Barlow';
  font-style: normal;
  font-weight: 400;
  src: url(https://fonts.gstatic.com/s/barlow/latin.woff2) format('woff2');
  unicode-range: U+0000-00FF;
}
"""


@pytest.fixture
def offline_fonts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replaces the transport, so the command runs end to end without a network."""
    requested: list[str] = []

    def fake_fetch(url: str, *, browser: bool = False) -> bytes:
        requested.append(url)
        if url == fetch_fonts.GOOGLE_CSS_URL:
            return CSS2_RESPONSE.encode("utf-8")
        if url == fetch_fonts.OFL_URL:
            return b"OFL text"
        return b"woff2-bytes"

    monkeypatch.setattr(fetch_fonts, "fetch", fake_fetch)
    return requested


def test_fetch_fonts_writes_the_faces_the_licence_and_the_stylesheet(tmp_path: Path, offline_fonts: list[str]):
    assert main(["fetch-fonts", "--module-dir", str(tmp_path)]) == 0

    css_dir = tmp_path / "website" / "src" / "css"
    assert (css_dir / "fonts" / "barlow-400-latin.woff2").read_bytes() == b"woff2-bytes"
    assert (css_dir / "fonts" / "OFL.txt").read_bytes() == b"OFL text"
    css = (css_dir / "fonts.css").read_text(encoding="utf-8")
    assert "@font-face" in css and "Open Font License" in css
    assert fetch_fonts.GOOGLE_CSS_URL in offline_fonts


def test_fetch_fonts_fails_rather_than_emptying_the_stylesheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(fetch_fonts, "fetch", lambda url, browser=False: b"/* nothing parseable */")
    assert main(["fetch-fonts", "--module-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "website" / "src" / "css" / "fonts.css").exists()
    assert "No woff2" in capsys.readouterr().err


# module entry point


def test_running_the_package_as_a_module_dispatches(tmp_path: Path, offline_fonts: list[str]):
    # In-process, so coverage sees it: the subprocess version in test_cli.py it cannot.
    import runpy

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("rdl_tools", run_name="__main__", alter_sys=True)
    assert raised.value.code == 2  # no subcommand given
