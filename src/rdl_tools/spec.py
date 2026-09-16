"""Shared spec/ and .env loading, used by every generator and by `rdl-tools init`."""

from __future__ import annotations

import re
import sys
from enum import StrEnum
from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef


class SpecKind(StrEnum):
    """What a spec/ file is, decided by its filename alone."""

    ONTOLOGY = "ontology"
    SHAPES = "shapes"
    LEDGER = "ledger"
    UNSUPPORTED = "unsupported"


VERSION_DIR_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PREFIX_DECL_RE = re.compile(r"^\s*@prefix\s+([A-Za-z0-9_.\-]*):\s*<([^>]*)>\s*\.", re.MULTILINE)


def local_name(iri: str) -> str:
    """The trailing name of an IRI, after the last '/' or '#'."""
    return re.split(r"[/#]", iri.rstrip("/#"))[-1]


def semver_key(dirname: str) -> tuple[int, int, int] | None:
    """Sort key for a `v1.2.3` directory name, or None if it isn't one."""
    match = VERSION_DIR_RE.match(dirname)
    if match is None:
        return None
    major, minor, patch = (int(g) for g in match.groups())
    return major, minor, patch


def version_key(version: str) -> tuple[int, int, int]:
    """Sort key for a bare `1.2.3` version string. Non-semver sorts last."""
    match = SEMVER_RE.match(version)
    if match is None:
        return (0, 0, 0)
    major, minor, patch = (int(g) for g in match.groups())
    return major, minor, patch


def find_previous_pin(static_dir: Path, exclude_version: str) -> Path | None:
    """The highest `v{semver}` pin directory in website/static/, ignoring v0 and the new pin."""
    candidates = []
    if not static_dir.exists():
        return None
    for child in static_dir.iterdir():
        if not child.is_dir() or child.name in (f"v{exclude_version}", "v0"):
            continue
        key = semver_key(child.name)
        if key is not None:
            candidates.append((key, child))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


# spec/ is curated, and everything in it is merged into the published graph, so the filename rule
# is an allow-list: `<stem>.ttl`, or a compound suffix named here with a handler. See ADR-004.
SUPPORTED_COMPOUND_SUFFIXES = {"shacl.ttl": SpecKind.SHAPES, "generated.ttl": SpecKind.LEDGER}


def classify_spec_file(path: Path) -> SpecKind:
    """A spec/ file's kind by filename alone."""
    parts = path.name.split(".")
    if len(parts) < 2 or parts[-1] != "ttl":
        return SpecKind.UNSUPPORTED
    if len(parts) == 2:
        return SpecKind.ONTOLOGY if parts[0] else SpecKind.UNSUPPORTED
    return SUPPORTED_COMPOUND_SUFFIXES.get(".".join(parts[-2:]), SpecKind.UNSUPPORTED)


def spec_files_of_kind(spec_dir: Path, kind: SpecKind) -> list[Path]:
    return sorted(f for f in spec_dir.glob("*.ttl") if classify_spec_file(f) is kind)


def ontology_files(spec_dir: Path) -> list[Path]:
    return spec_files_of_kind(spec_dir, SpecKind.ONTOLOGY)


def shape_files(spec_dir: Path) -> list[Path]:
    return spec_files_of_kind(spec_dir, SpecKind.SHAPES)


def ledger_files(spec_dir: Path) -> list[Path]:
    return spec_files_of_kind(spec_dir, SpecKind.LEDGER)


def unsupported_files(spec_dir: Path) -> list[Path]:
    return spec_files_of_kind(spec_dir, SpecKind.UNSUPPORTED)


def supported_names_hint() -> str:
    listed = ", ".join(f"<stem>.{suffix}" for suffix in sorted(SUPPORTED_COMPOUND_SUFFIXES))
    return f"<stem>.ttl, {listed}"


def require_supported_spec_files(spec_dir: Path) -> None:
    """Exit 2, naming each file, when spec/ holds Turtle the build has no handler for."""
    offenders = unsupported_files(spec_dir)
    if not offenders:
        return
    for path in offenders:
        print(
            f"{path} is not a supported spec/ file name. spec/ holds ontology and shapes only; "
            f"supported names are {supported_names_hint()}. Move it out of spec/.",
            file=sys.stderr,
        )
    raise SystemExit(2)


def merge_ontology(spec_dir: Path) -> Graph:
    graph = Graph()
    require_supported_spec_files(spec_dir)
    files = ontology_files(spec_dir)
    if not files:
        print(f"No ontology .ttl files found in {spec_dir}", file=sys.stderr)
        raise SystemExit(2)
    for f in files:
        graph.parse(f, format="turtle")
    require_single_ontology(graph, spec_dir)
    return graph


def require_single_ontology(graph: Graph, spec_dir: Path) -> URIRef:
    """The one owl:Ontology subject in the merged graph, or exit 2.

    Generators take the first subject rdflib yields, and that order is not stable, so a second
    owl:Ontology node makes the published IRI and every derived URL non-deterministic.
    """
    subjects = sorted({str(s) for s in graph.subjects(RDF.type, OWL.Ontology)})
    if not subjects:
        print(f"No owl:Ontology subject found in {spec_dir}/*.ttl", file=sys.stderr)
        raise SystemExit(2)
    if len(subjects) > 1:
        listed = "\n  ".join(subjects)
        print(
            f"{len(subjects)} owl:Ontology subjects in the merged graph from {spec_dir}/*.ttl:\n"
            f"  {listed}\n"
            "A module publishes exactly one ontology IRI. Keep one owl:Ontology node and give the "
            "others another type, or move them out of spec/.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return URIRef(subjects[0])


def merge_shapes(spec_dir: Path) -> Graph:
    graph = Graph()
    require_supported_spec_files(spec_dir)
    for f in shape_files(spec_dir):
        graph.parse(f, format="turtle")
    return graph


def declared_prefixes(paths: list[Path]) -> list[tuple[str, str]]:
    """The `@prefix` declarations read from the file text, in declaration order, deduplicated.

    Not Graph.namespaces(): rdflib binds prefixes the module never declared, and the published
    Namespaces table is meant to be exactly what the source files declare.
    """
    seen: dict[str, str] = {}
    for path in paths:
        for prefix, uri in PREFIX_DECL_RE.findall(path.read_text(encoding="utf-8")):
            if prefix and prefix not in seen:
                seen[prefix] = uri
    return list(seen.items())


def read_env(module_dir: Path) -> dict[str, str]:
    """Parse .env into a dict. Inline ` # comment` tails are stripped, matching dotenv."""
    env: dict[str, str] = {}
    env_path = module_dir / ".env"
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = re.sub(r"\s+#.*$", "", value).strip().strip("\"'")
        env[key.strip()] = value
    return env


def write_generated(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings on every platform.

    `Path.write_text` defaults to `newline=None`, which turns every `\\n` into `os.linesep` — so
    generating on Windows would commit CRLF and diff against what Linux CI regenerates.
    """
    path.write_text(text, encoding="utf-8", newline="\n")
