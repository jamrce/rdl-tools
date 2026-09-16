"""`rdl-tools render-docs` — render the website/static/v{version}/ont/ artifact tree.

Stamps version metadata onto the merged spec/ graph and writes ont.ttl/ont.rdf/ont.jsonld/ont.nt
into the pin (refused on overwrite) and into v0/, which is rebuilt wholesale as "whatever is
latest". Only each pin's ont.ttl is committed; see docs/adrs/ADR-002.

The index.html both directories also serve is the built Docusaurus reference page. Nothing here
writes it.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from rdflib import OWL, RDF, Graph, Literal, URIRef

from ..spec import find_previous_pin, ledger_files, merge_ontology


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--module-dir", default=".", help="Module repo root (default: cwd)")
    parser.add_argument("--version", required=True, help="Release version, e.g. 0.1.0 (no 'v' prefix)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing pin directory")


def stamp_version(
    graph: Graph,
    ontology_iri: URIRef,
    pin_iri: URIRef,
    version: str,
    prior_pin_iri: URIRef | None,
) -> None:
    graph.set((ontology_iri, OWL.versionIRI, pin_iri))
    graph.set((ontology_iri, OWL.versionInfo, Literal(version)))
    if prior_pin_iri is not None:
        graph.set((ontology_iri, OWL.priorVersion, prior_pin_iri))


def write_artifact_tree(out_dir: Path, graph: Graph, ledger_src: Path | None) -> None:
    """The serialisations only. index.html at the same path is the built Docusaurus page."""
    ont_dir = out_dir / "ont"
    ont_dir.mkdir(parents=True, exist_ok=True)
    # encoding is explicit: the N-Triples serializer warns when it has to assume UTF-8.
    graph.serialize(destination=str(ont_dir / "ont.ttl"), format="turtle", encoding="utf-8")
    graph.serialize(destination=str(ont_dir / "ont.rdf"), format="xml", encoding="utf-8")
    graph.serialize(destination=str(ont_dir / "ont.jsonld"), format="json-ld", encoding="utf-8")
    graph.serialize(destination=str(ont_dir / "ont.nt"), format="nt", encoding="utf-8")
    if ledger_src is not None:
        shutil.copyfile(ledger_src, ont_dir / "ledger.ttl")


def find_ledger(spec_dir: Path) -> Path | None:
    found = ledger_files(spec_dir)
    return found[0] if found else None


def run(args: argparse.Namespace) -> int:
    module_dir = Path(args.module_dir).resolve()
    version = args.version.lstrip("v")

    spec_dir = module_dir / "spec"
    static_dir = module_dir / "website" / "static"
    pin_dir = static_dir / f"v{version}"
    v0_dir = static_dir / "v0"

    if pin_dir.exists() and not args.force:
        print(f"{pin_dir} already exists — pins are immutable. Pass --force to override.", file=sys.stderr)
        return 1

    graph = merge_ontology(spec_dir)

    ontology_iri = next(graph.subjects(RDF.type, OWL.Ontology), None)
    if not isinstance(ontology_iri, URIRef):
        print("No owl:Ontology subject found in spec/*.ttl", file=sys.stderr)
        return 2

    previous_pin = find_previous_pin(static_dir, version)

    base_iri = str(ontology_iri)
    if "/v0/ont" not in base_iri:
        print(f"owl:Ontology subject {base_iri!r} doesn't match the expected '.../v0/ont' shape.", file=sys.stderr)
        return 2
    pin_iri = URIRef(base_iri.replace("/v0/ont", f"/v{version}/ont"))
    prior_pin_iri = None
    if previous_pin is not None:
        prior_version = previous_pin.name[1:]
        prior_pin_iri = URIRef(base_iri.replace("/v0/ont", f"/v{prior_version}/ont"))

    stamp_version(graph, ontology_iri, pin_iri, version, prior_pin_iri)

    ledger_src = find_ledger(spec_dir)

    write_artifact_tree(pin_dir, graph, ledger_src)
    shutil.rmtree(v0_dir, ignore_errors=True)
    write_artifact_tree(v0_dir, graph, ledger_src)

    print(f"Wrote {pin_dir}/ont/ and {v0_dir}/ont/")
    return 0
