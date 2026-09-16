"""Find and classify .ttl files for `rdl-tools init`. See docs/adrs/ADR-004.

Discovery order: `spec/*.ttl`, loose `*.ttl` at the folder root, `website/static/v*/ont/*.ttl`,
then `--from <dir>`. Classification is by content, never by filename.

Version resolution tries, in order: `owl:versionInfo`, the `owl:versionIRI` version segment,
`X.Y.Z` in the filename, then `dcterms:modified` / `dcterms:created`. Each candidate records which
source won, so the caller can confirm before anything is baked into an immutable pin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rdflib import DCTERMS, OWL, RDF, Graph, URIRef
from rdflib.namespace import SH

# Unanchored, unlike spec.SEMVER_RE: this one searches a label or filename for a triple.
SEMVER_SEARCH_RE = re.compile(r"(\d+\.\d+\.\d+)")


class ContentKind(StrEnum):
    """What a discovered `.ttl` file is, decided by its content."""

    ONTOLOGY = "ontology"
    SHAPES = "shapes"
    UNSUPPORTED = "unsupported"


@dataclass
class Candidate:
    """One discovered `.ttl` file, parsed and classified."""

    path: Path
    graph: Graph
    kind: ContentKind
    source: str  # where it was discovered: "spec", "root", "static-pin", "from"

    version: str | None = None
    version_source: str | None = None  # "versionInfo" | "versionIRI" | "filename" | "modified" | "created"
    version_problem: str | None = None  # set when a version label needed normalising or was refused


def is_shapes_content(graph: Graph) -> bool:
    """True when the graph asserts at least one `sh:NodeShape` — the content-based shapes test."""
    return next(graph.subjects(RDF.type, SH.NodeShape), None) is not None


def is_ontology_content(graph: Graph) -> bool:
    """True when the graph asserts at least one `owl:Ontology` subject."""
    return next(graph.subjects(RDF.type, OWL.Ontology), None) is not None


def classify_content(graph: Graph) -> ContentKind:
    """A candidate's kind by content. Shapes win over ontology: a file carrying both is shapes."""
    if is_shapes_content(graph):
        return ContentKind.SHAPES
    if is_ontology_content(graph):
        return ContentKind.ONTOLOGY
    return ContentKind.UNSUPPORTED


def parse_ttl(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def classify(path: Path, source: str) -> Candidate:
    graph = parse_ttl(path)
    return Candidate(path=path, graph=graph, kind=classify_content(graph), source=source)


def discover_root_files(module_dir: Path) -> list[Path]:
    return sorted(module_dir.glob("*.ttl"))


def discover_spec_files(module_dir: Path) -> list[Path]:
    spec_dir = module_dir / "spec"
    if not spec_dir.is_dir():
        return []
    return sorted(spec_dir.glob("*.ttl"))


def discover_static_pins(module_dir: Path) -> list[Path]:
    static_dir = module_dir / "website" / "static"
    if not static_dir.is_dir():
        return []
    return sorted(static_dir.glob("v*/ont/*.ttl"))


def discover_from_dir(from_dir: Path) -> list[Path]:
    return sorted(from_dir.glob("*.ttl"))


def discover_all(module_dir: Path, from_dir: Path | None = None) -> list[Candidate]:
    """Every candidate `.ttl` file, classified, in priority order. Does not resolve versions."""
    candidates: list[Candidate] = []
    for path in discover_spec_files(module_dir):
        candidates.append(classify(path, "spec"))
    for path in discover_root_files(module_dir):
        candidates.append(classify(path, "root"))
    for path in discover_static_pins(module_dir):
        candidates.append(classify(path, "static-pin"))
    if from_dir is not None:
        for path in discover_from_dir(from_dir):
            candidates.append(classify(path, "from"))
    return candidates


def normalize_semver(label: str) -> tuple[str | None, str | None]:
    """Leading `X.Y.Z` out of a version label, or (None, problem) when none is found.

    `"0.2.0 (RC2)"` normalises to `0.2.0`; a label with no `X.Y.Z` triple is refused, not guessed.
    """
    match = SEMVER_SEARCH_RE.search(label)
    if match is None:
        return None, f"{label!r} contains no X.Y.Z version"
    normalized = match.group(1)
    if normalized != label.strip():
        return normalized, f"normalised {label!r} to {normalized!r}"
    return normalized, None


def _version_iri_segment(iri: str) -> str | None:
    """The version segment of an `owl:versionIRI`, e.g. `.../v0.5.7/ont` -> `0.5.7`."""
    for segment in iri.split("/"):
        if segment.startswith("v") and SEMVER_SEARCH_RE.fullmatch(segment[1:]):
            return segment[1:]
    return None


def _filename_version(path: Path) -> str | None:
    match = SEMVER_SEARCH_RE.search(path.stem)
    return match.group(1) if match else None


def resolve_version(candidate: Candidate) -> None:
    """Fill in `candidate.version` / `version_source` / `version_problem` in place, per the
    priority order. Never raises — a version that cannot be resolved is left None, with the
    problem recorded, so the caller can refuse or ask rather than guess."""
    graph = candidate.graph
    ontology = next(graph.subjects(RDF.type, OWL.Ontology), None)

    raw: str | None = None
    source: str | None = None
    if ontology is not None:
        version_info = next(graph.objects(ontology, OWL.versionInfo), None)
        if version_info is not None:
            raw, source = str(version_info), "versionInfo"
        else:
            version_iri = next(graph.objects(ontology, OWL.versionIRI), None)
            if version_iri is not None:
                segment = _version_iri_segment(str(version_iri))
                if segment is not None:
                    candidate.version = segment
                    candidate.version_source = "versionIRI"
                    return

    if raw is None:
        filename_version = _filename_version(candidate.path)
        if filename_version is not None:
            candidate.version = filename_version
            candidate.version_source = "filename"
            return

    if raw is None and ontology is not None:
        for predicate, label in ((DCTERMS.modified, "modified"), (DCTERMS.created, "created")):
            value = next(graph.objects(ontology, predicate), None)
            if value is not None:
                raw, source = str(value), label
                break

    if raw is None:
        candidate.version_problem = "no owl:versionInfo, owl:versionIRI, filename or date to derive a version from"
        return

    normalized, problem = normalize_semver(raw)
    candidate.version = normalized
    candidate.version_source = source
    candidate.version_problem = problem


def ontology_subjects(graph: Graph) -> list[URIRef]:
    return sorted({s for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef)}, key=str)
