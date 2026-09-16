"""`rdl-tools expand-pins` — rebuild the derived half of the published artifact tree.

    v{version}/ont/ont.rdf, ont.jsonld, ont.nt    re-serialised from that pin's committed ont.ttl
    v0/ont/                                       a whole copy of the newest pin

Graph-identical to what `render-docs` wrote, not byte-identical: rdflib reorders on every
serialisation. See docs/adrs/ADR-002.

Run before `npm run build` or `npm start` in a fresh checkout, or every download link 404s. Safe
to re-run; it only ever overwrites derived files.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from rdflib import Graph

from ..spec import semver_key

# Written beside each pin's ont.ttl. ont.ttl itself is committed, never regenerated here.
DERIVED_FORMATS = (("ont.rdf", "xml"), ("ont.jsonld", "json-ld"), ("ont.nt", "nt"))


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--module-dir", default=".", help="Module repo root (default: cwd)")


def pin_dirs(static_dir: Path) -> list[Path]:
    """Every committed `v{semver}` pin, oldest first. v0 is derived, so never one of these."""
    found: list[tuple[tuple[int, ...], Path]] = []
    for child in sorted(static_dir.iterdir()) if static_dir.is_dir() else []:
        key = semver_key(child.name) if child.is_dir() else None
        if key is not None and (child / "ont" / "ont.ttl").exists():
            found.append((key, child))
    return [pin for _, pin in sorted(found, key=lambda pair: pair[0])]


def expand(pin: Path) -> list[Path]:
    """Write the derived serialisations beside a pin's committed ont.ttl."""
    ont_dir = pin / "ont"
    graph = Graph()
    graph.parse(ont_dir / "ont.ttl", format="turtle")
    written = []
    for name, fmt in DERIVED_FORMATS:
        # encoding is explicit: the N-Triples serializer warns when it has to assume UTF-8.
        graph.serialize(destination=str(ont_dir / name), format=fmt, encoding="utf-8")
        written.append(ont_dir / name)
    return written


def copy_to_v0(pin: Path, static_dir: Path) -> None:
    """Replace v0/ont/ with a plain copy of the newest pin's ont/ directory.

    Rebuilt wholesale, never merged: a term retired in the newest release must disappear from v0.
    """
    v0_ont = static_dir / "v0" / "ont"
    shutil.rmtree(static_dir / "v0", ignore_errors=True)
    shutil.copytree(pin / "ont", v0_ont)


def run(args: argparse.Namespace) -> int:
    static_dir = Path(args.module_dir).resolve() / "website" / "static"
    pins = pin_dirs(static_dir)
    if not pins:
        # The normal state before the first release: the staging docs own /v0/ont/, and there is
        # no artifact tree to expand yet.
        print(f"No pins with a committed ont.ttl under {static_dir} — nothing to expand.")
        return 0

    for pin in pins:
        expand(pin)
        print(f"Expanded {pin.name}/ont/ ({', '.join(name for name, _ in DERIVED_FORMATS)})")

    copy_to_v0(pins[-1], static_dir)
    print(f"Rebuilt v0/ont/ from {pins[-1].name}")
    return 0
