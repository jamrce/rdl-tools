"""Finish local setup once `init` has written `.env` and `spec/`.

Renames `github/workflows/` to `.github/workflows/`, activating the template's CI, then installs
the Python and npm dependencies. `--skip-install` skips the installs for CI and offline runs.
Every step is local and reversible; the only network access is to package registries.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def activate_workflows(module_dir: Path) -> Path | None:
    """Rename `github/workflows/` to `.github/workflows/`. None when already done, or nothing to do."""
    source = module_dir / "github"
    dest = module_dir / ".github"
    if not source.is_dir() or dest.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    source.rename(dest)
    return dest


def create_venv(module_dir: Path) -> Path:
    venv_dir = module_dir / ".venv"
    if not venv_dir.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    return venv_dir


def venv_python(venv_dir: Path) -> Path:
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def pip_install(module_dir: Path, venv_dir: Path) -> None:
    requirements = module_dir / "requirements.txt"
    if not requirements.exists():
        return
    command = [str(venv_python(venv_dir)), "-m", "pip", "install", "-r", str(requirements)]
    # RDL_TOOLS_INDEX_URL lets a pre-release rehearsal resolve the module's pinned rdl-tools from
    # TestPyPI while its dependencies still come from PyPI.
    index_url = os.environ.get("RDL_TOOLS_INDEX_URL")
    if index_url:
        command += ["--index-url", index_url, "--extra-index-url", "https://pypi.org/simple"]
    subprocess.run(command, check=True, cwd=module_dir)


WINDOWS_SHIM_SUFFIXES = (".cmd", ".ps1", ".exe")


def node_modules_platform_mismatch(website_dir: Path) -> str | None:
    """Detect a `node_modules/` installed by a different OS on the same checkout.

    `.bin/` entries are platform-specific, and the wrong ones there are what make `npm run start`
    fail with `exec: node.exe: not found`. Checked without running npm.
    """
    node_modules = website_dir / "node_modules"
    bin_dir = node_modules / ".bin"
    if not bin_dir.is_dir():
        return None
    entries = [e for e in bin_dir.iterdir() if not e.is_dir()]
    if not entries:
        return None

    # npm on Windows writes an extensionless shim *beside* each .cmd/.ps1, so the absence of any
    # Windows shim is the signal, never the presence of an extensionless entry.
    windows_shims = [e for e in entries if e.suffix.lower() in WINDOWS_SHIM_SUFFIXES]
    if platform.system() == "Windows":
        if not windows_shims:
            return f"{node_modules} looks POSIX-installed (no .cmd shims) — reinstall on this OS"
        return None
    if windows_shims:
        return f"{node_modules} looks Windows-installed (found {windows_shims[0].name}) — reinstall on this OS"
    return None


def npm_install(website_dir: Path, *, reinstall: bool = False) -> None:
    if reinstall:
        node_modules = website_dir / "node_modules"
        if node_modules.is_dir():
            shutil.rmtree(node_modules)
    # Resolved, not passed as a bare name: on Windows npm is npm.cmd, and CreateProcess does not
    # consult PATHEXT. shutil.which does.
    npm = shutil.which("npm")
    if npm is None:
        raise FileNotFoundError("npm is not on PATH. Install Node, or pass --skip-install.")
    subprocess.run([npm, "install"], check=True, cwd=website_dir)


def finish_setup(module_dir: Path, *, skip_install: bool = False) -> list[str]:
    """Run every local-setup step, returning notes for the caller to print."""
    notes: list[str] = []

    activated = activate_workflows(module_dir)
    if activated is not None:
        notes.append(f"Activated CI: renamed github/workflows/ to {activated}")

    if skip_install:
        notes.append("--skip-install: leaving .venv/ and node_modules/ untouched")
        return notes

    venv_dir = create_venv(module_dir)
    pip_install(module_dir, venv_dir)
    notes.append(f"Python dependencies installed into {venv_dir}")

    website_dir = module_dir / "website"
    if website_dir.is_dir():
        mismatch = node_modules_platform_mismatch(website_dir)
        if mismatch is not None:
            notes.append(f"node_modules mismatch detected — reinstalling: {mismatch}")
            npm_install(website_dir, reinstall=True)
        else:
            npm_install(website_dir)
        notes.append(f"Node dependencies installed into {website_dir / 'node_modules'}")

    return notes
