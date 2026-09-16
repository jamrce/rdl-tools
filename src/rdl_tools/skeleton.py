"""Recognise a module checkout, and refuse to configure anything else. See docs/adrs/ADR-001."""

from __future__ import annotations

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


def missing_parts(module_dir: Path) -> list[str]:
    return [name for name in REQUIRED if not (module_dir / name).exists()]


def explain(module_dir: Path, missing: list[str]) -> str:
    return MISSING_SKELETON.format(module_dir=module_dir, missing=" or ".join(missing))
