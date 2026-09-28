"""Recognise a module checkout, and refuse to configure or build anything else. See docs/adrs/ADR-001."""

from __future__ import annotations

import sys
from pathlib import Path

# Present before rdl-tools touches a checkout. Not `spec/`: it may be empty, with the ontology
# still at the folder root. `website/` is what separates a module from a bare folder of Turtle.
REQUIRED = ("website", "requirements.txt")

MISSING_SKELETON = (
    "{module_dir} does not look like a module repo: no {missing}.\n"
    "\n"
    "rdl-tools configures and builds a module; it does not create one. Start from the template:\n"
    "\n"
    "  https://github.com/jamrce/rdl-module-template  ->  Use this template\n"
    "\n"
    "then clone your new repository and run this command inside it."
)

# For the build commands, which a module maintainer most often reaches from the wrong folder.
NOT_A_MODULE = "{module_dir} is not a module folder: no {missing}. Run from the module root or pass --module-dir."


def missing_parts(module_dir: Path) -> list[str]:
    return [name for name in REQUIRED if not (module_dir / name).exists()]


def explain(module_dir: Path, missing: list[str]) -> str:
    return MISSING_SKELETON.format(module_dir=module_dir, missing=" or ".join(missing))


def require_module(module_dir: Path) -> None:
    """Exit 2 unless `module_dir` is a module checkout. `init` explains the template instead."""
    missing = missing_parts(module_dir)
    if missing:
        print(NOT_A_MODULE.format(module_dir=module_dir, missing=" or ".join(missing)), file=sys.stderr)
        raise SystemExit(2)
