"""`rdl-tools format` — canonicalise an ontology file's Turtle serialisation.

    rdl-tools format --spec-dir spec              # rewrite every ontology file in place
    rdl-tools format --check --spec-dir spec      # CI gate, no writes
    rdl-tools format --ontology spec/common.ttl   # one named file

A graph round-trip, so nothing that is not a triple survives it: `#` comments and unused prefix
declarations are dropped. Published pins under website/static/ are refused outright.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph

from ..spec import (
    classify_spec_file,
    ontology_files,
    require_supported_spec_files,
    supported_names_hint,
    write_generated,
)

# Reformatting a published pin rewrites bytes a w3id URL has already served.
IMMUTABLE_PARTS = ("website", "static")


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ontology", help="One ontology TTL file (default: every one in --spec-dir)")
    parser.add_argument("--spec-dir", default="spec", help="Directory of ontology files (default: spec)")
    parser.add_argument("--check", action="store_true", help="Only check formatting; write nothing")


def is_published_pin(path: Path) -> bool:
    parts = path.resolve().parts
    return any(parts[i : i + 2] == IMMUTABLE_PARTS for i in range(len(parts) - 1))


def normalize_turtle(input_path: Path) -> str:
    """The canonical Turtle for a file. Idempotent: normalize(normalize(x)) == normalize(x)."""
    graph = Graph()
    graph.parse(input_path, format="turtle")
    return graph.serialize(format="turtle")


def targets(args: argparse.Namespace) -> list[Path] | None:
    """The files to act on, or None when the arguments name nothing that exists."""
    if args.ontology:
        path = Path(args.ontology)
        if not path.exists():
            print(f"{path} does not exist.", file=sys.stderr)
            return None
        # The ledger is another tool's output, so it is refused here as well as in the sweep.
        if classify_spec_file(path) not in ("ontology", "shapes"):
            print(
                f"{path} is not a file this command formats; it takes {supported_names_hint()} "
                "other than the generated ledger.",
                file=sys.stderr,
            )
            return None
        return [path]

    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        print(f"{spec_dir} is not a directory.", file=sys.stderr)
        return None
    require_supported_spec_files(spec_dir)
    found = ontology_files(spec_dir)
    if not found:
        print(f"No ontology .ttl files found in {spec_dir}.", file=sys.stderr)
        return None
    return found


def run(args: argparse.Namespace) -> int:
    paths = targets(args)
    if paths is None:
        return 2

    failures: list[Path] = []
    for path in paths:
        if is_published_pin(path):
            print(
                f"{path} is inside website/static/ — published artifacts are byte-immutable "
                "and are never reformatted. Format the source in spec/ instead.",
                file=sys.stderr,
            )
            return 2

        normalized = normalize_turtle(path)
        if path.read_text(encoding="utf-8") == normalized:
            continue
        if args.check:
            failures.append(path)
            continue
        write_generated(path, normalized)
        print(f"Reformatted {path}")

    if args.check:
        if failures:
            for path in failures:
                print(f"{path} is not canonically formatted.", file=sys.stderr)
            print("Formatting check failed. Run `rdl-tools format` without --check.", file=sys.stderr)
            return 1
        print(f"Formatting check passed ({len(paths)} file(s)).")
        return 0

    print(f"Ontology formatting up to date ({len(paths)} file(s)).")
    return 0
