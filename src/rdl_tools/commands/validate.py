"""`rdl-tools validate` — validate the ontology in spec/, and its SHACL shapes when it has any.

Three gates, in order:

1. Every ontology file parses, and the merged graph carries exactly one owl:Ontology subject.
2. No ontology file asserts sh:NodeShape — shapes there validate nothing and publish inside the
   ontology graph. They belong in a *.shacl.ttl file.
3. The data graph conforms to the merged shapes. Skipped with a notice when there are no shapes.

Gate 3 resolves `owl:imports` by default: each imported IRI is dereferenced over the network and
merged in, so shapes targeting a class defined upstream see that class's hierarchy. Pass
`--no-imports` to skip it. Use that offline, in a sandboxed runner, or whenever the module's own
axioms are enough to validate against — an import that does not resolve is simply not merged, and
a constraint that depended on it may then report differently.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import RDF, Graph
from rdflib.namespace import SH

from ..spec import merge_ontology, ontology_files, require_supported_spec_files, shape_files


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--spec-dir",
        default="spec",
        help="Directory holding {module}.ttl and {module}.shacl.ttl (default: spec)",
    )
    parser.add_argument(
        "--no-imports",
        action="store_true",
        help="Skip owl:imports resolution, which otherwise dereferences each imported IRI over the network",
    )


def shape_asserting_files(paths: list[Path]) -> list[Path]:
    """Ontology files that declare an sh:NodeShape — misplaced shapes (gate 2)."""
    offenders = []
    for path in paths:
        graph = Graph()
        graph.parse(path, format="turtle")
        if next(graph.subjects(RDF.type, SH.NodeShape), None) is not None:
            offenders.append(path)
    return offenders


def run(args: argparse.Namespace) -> int:
    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        print(f"{spec_dir} is not a directory.", file=sys.stderr)
        return 2

    require_supported_spec_files(spec_dir)

    ontology_paths = ontology_files(spec_dir)
    shapes_paths = shape_files(spec_dir)

    if not ontology_paths:
        print(f"No ontology .ttl files found in {spec_dir}.", file=sys.stderr)
        return 2

    data_graph = merge_ontology(spec_dir)

    misplaced = shape_asserting_files(ontology_paths)
    if misplaced:
        for path in misplaced:
            print(
                f"{path} asserts sh:NodeShape but is not named *.shacl.ttl. Shapes there are "
                "published inside the ontology graph and validate nothing — rename the file or "
                "move the shapes into {module}.shacl.ttl.",
                file=sys.stderr,
            )
        return 2

    if not shapes_paths:
        print(f"Ontology parsed. No *.shacl.ttl in {spec_dir} — SHACL validation skipped.")
        return 0

    shape_graph = Graph()
    for path in shapes_paths:
        shape_graph.parse(path, format="turtle")

    # Lazy: pyshacl pulls in owlrl and a SPARQL engine, which `--help` should not pay for.
    try:
        from pyshacl import validate as pyshacl_validate
    except ImportError as exc:  # pragma: no cover - environment fault, not a code path
        print(
            f"pyshacl is not importable in this environment ({exc}). It is a declared dependency, "
            "so this means a broken or partial install — reinstall with `pip install rdl-tools`.",
            file=sys.stderr,
        )
        return 2

    conforms, _, report_text = pyshacl_validate(
        data_graph,
        shacl_graph=shape_graph,
        inference="rdfs",
        do_owl_imports=not args.no_imports,
        serialize_report_graph="ttl",
    )

    if not conforms:
        print("SHACL validation failed.", file=sys.stderr)
        print(report_text.decode("utf-8") if isinstance(report_text, bytes) else str(report_text))
        return 1

    print("Validation passed.")
    return 0
