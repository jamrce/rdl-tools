"""`rdl-tools init` — configure a module checkout.

Derives every `.env` value it can from the `.ttl` on disk, prompts only for what RDF cannot
supply, registers historical pins, drafts a changelog per version, and finishes local setup.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rdflib import DCTERMS, OWL, RDF, Graph, Literal, URIRef

from .. import bootstrap, discover, envwrite, skeleton
from ..spec import local_name, version_key, write_generated
from . import render_docs, render_site_data

MANIFEST_NAME = ".rdl-tools-manifest.json"

NO_INPUT = (
    "rdl-tools init needs to ask a question, but stdin is closed — piped input, or no terminal.\n"
    "\n"
    "Run it in a terminal, or non-interactively with --yes, adding --repo-owner and --slug if it\n"
    "cannot derive them. `--clean` undoes a partial run."
)

Report = dict[str, Any]


class InitError(Exception):
    """A problem that stops `init` before it writes anything further."""


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--module-dir", default=".", help="Target folder (default: cwd)")
    parser.add_argument("--from", dest="from_dir", help="Directory of loose .ttl version snapshots to import")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing .env / spec / pin")
    parser.add_argument("--clean", action="store_true", help="Remove generated files only, then exit")
    parser.add_argument("--skip-install", action="store_true", help="Skip venv/npm install (CI, offline)")
    parser.add_argument("--yes", action="store_true", help="Assume yes to every confirmation (CI, scripting)")
    parser.add_argument("--repo-owner", help="REPO_OWNER, skips the prompt")
    parser.add_argument("--w3id-authority", help="W3ID_AUTHORITY, skips the prompt")
    parser.add_argument("--slug", help="MODULE_SLUG, skips derivation/confirmation")


# manifest


def write_manifest(module_dir: Path, derived: list[Path]) -> None:
    payload = {"derived": [str(p.relative_to(module_dir)) for p in derived]}
    write_generated(module_dir / MANIFEST_NAME, json.dumps(payload, indent=2) + "\n")


def read_manifest(module_dir: Path) -> Report | None:
    manifest_path = module_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None
    loaded: Report = json.loads(manifest_path.read_text(encoding="utf-8"))
    return loaded


def clean(module_dir: Path) -> list[Path]:
    """Remove exactly the files this tool generated (per the manifest), never hand-written ones."""
    manifest = read_manifest(module_dir)
    if manifest is None:
        return []
    removed = []
    for relative in manifest["derived"]:
        path = module_dir / relative
        if path.exists():
            path.unlink()
            removed.append(path)
    (module_dir / MANIFEST_NAME).unlink(missing_ok=True)
    return removed


# discovery + classification


UNSUPPORTED_CONTENT = (
    "asserts neither owl:Ontology nor sh:NodeShape, so it is neither an ontology source nor a shapes file"
)


def refuse_unsupported(candidates: list[discover.Candidate]) -> None:
    """Exit 2, naming each file, when a discovered `.ttl` is neither ontology nor shapes."""
    offenders = [c for c in candidates if c.kind is discover.ContentKind.UNSUPPORTED]
    if not offenders:
        return
    for candidate in offenders:
        print(
            f"{candidate.path} ({candidate.source}) {UNSUPPORTED_CONTENT}. "
            "Move it out of the module folder, or out of --from, and run init again.",
            file=sys.stderr,
        )
    raise SystemExit(2)


def classify_and_merge(
    candidates: list[discover.Candidate],
) -> tuple[Graph, Graph, list[discover.Candidate]]:
    """Merge every candidate's graph into an ontology graph and a shapes graph, by content.

    Raises InitError when the merged ontology graph carries more than one `owl:Ontology` subject.
    """
    ontology_graph = Graph()
    shapes_graph = Graph()
    for candidate in candidates:
        if candidate.kind is discover.ContentKind.SHAPES:
            # Union: shapes carry no version, so there is no per-version home. See ADR-004.
            shapes_graph += candidate.graph
        elif candidate.kind is discover.ContentKind.ONTOLOGY:
            ontology_graph += candidate.graph

    subjects = sorted({str(s) for s in ontology_graph.subjects(RDF.type, OWL.Ontology)})
    if len(subjects) > 1:
        listed = "\n  ".join(subjects)
        raise InitError(
            f"{len(subjects)} owl:Ontology subjects across the discovered files:\n  {listed}\n"
            "A module publishes exactly one ontology IRI."
        )
    return ontology_graph, shapes_graph, candidates


def refuse_duplicate_versions(ontology_candidates: list[discover.Candidate]) -> None:
    """Refuse, by name, two ontology candidates resolving to one version — both claim one pin."""
    seen: dict[str, list[Path]] = {}
    for candidate in ontology_candidates:
        seen.setdefault(candidate.version or "", []).append(candidate.path)
    clashes = {version: paths for version, paths in seen.items() if len(paths) > 1}
    if not clashes:
        return
    listed = "\n  ".join(f"{version}: {', '.join(p.name for p in paths)}" for version, paths in sorted(clashes.items()))
    raise InitError(
        f"Two or more ontology files resolve to the same version:\n  {listed}\n"
        "One version, one file. Remove or re-version the duplicate."
    )


def rename_shapes_files(candidates: list[discover.Candidate]) -> list[tuple[Path, Path]]:
    """Files classified as shapes by content but not already named `*.shacl.ttl`."""
    renames = []
    for candidate in candidates:
        if candidate.kind is discover.ContentKind.SHAPES and not candidate.path.name.endswith(".shacl.ttl"):
            new_path = candidate.path.with_name(candidate.path.stem + ".shacl.ttl")
            renames.append((candidate.path, new_path))
    return renames


# the flow


def ask(question: str) -> str:
    """The default prompt. Named, not `input` itself, so a test can stand in for it."""
    return input(question)


def warn(message: str) -> None:
    """Diagnostics go to stderr; stdout carries the run's own report."""
    print(f"warning: {message}", file=sys.stderr)


def run_init(
    module_dir: Path,
    *,
    from_dir: Path | None = None,
    force: bool = False,
    do_clean: bool = False,
    skip_install: bool = False,
    assume_yes: bool = False,
    repo_owner: str | None = None,
    w3id_authority: str | None = None,
    slug: str | None = None,
    prompt: Callable[[str], str] = ask,
    out: Callable[..., None] = print,
) -> Report:
    """Run the full `init` flow, returning a report dict describing what happened."""
    module_dir = module_dir.resolve()

    if do_clean:
        removed = clean(module_dir)
        out(f"--clean: removed {len(removed)} generated file(s).")
        return {"cleaned": [str(p) for p in removed]}

    manifest = read_manifest(module_dir)
    if manifest is not None and not force:
        out(f"{module_dir} was already initialised by rdl-tools (see {MANIFEST_NAME}). Nothing to do.")
        return {"noop": True}

    report: Report = {}

    missing = skeleton.missing_parts(module_dir)
    if missing:
        print(skeleton.explain(module_dir, missing), file=sys.stderr)
        raise SystemExit(2)

    # Discover, classify, merge, refuse more than one ontology.
    candidates = discover.discover_all(module_dir, from_dir)
    if not candidates:
        out("No .ttl files found (spec/, folder root, website/static/v*/ont/, or --from). Nothing to derive.")
        write_manifest(module_dir, [])
        bootstrap.finish_setup(module_dir, skip_install=skip_install)
        return report

    refuse_unsupported(candidates)
    ontology_graph, shapes_graph, candidates = classify_and_merge(candidates)

    renames = rename_shapes_files(candidates)
    if renames:
        out("Files classified as SHACL shapes by content, to be renamed:")
        for old, new in renames:
            out(f"  {old.name} -> {new.name}")
        if assume_yes or prompt("Rename? [Y/n] ").strip().lower() not in ("n", "no"):
            for old, new in renames:
                old.rename(new)
                for candidate in candidates:
                    if candidate.path == old:
                        candidate.path = new

    # Resolve version keys, always confirmed.
    for candidate in candidates:
        discover.resolve_version(candidate)
    unresolved = [c for c in candidates if c.kind is discover.ContentKind.ONTOLOGY and c.version is None]
    if unresolved:
        names = ", ".join(c.path.name for c in unresolved)
        raise InitError(f"Could not resolve a version for: {names}. Refusing to guess.")

    out("Resolved versions:")
    for candidate in candidates:
        if candidate.kind is not discover.ContentKind.ONTOLOGY:
            continue
        note = f" ({candidate.version_problem})" if candidate.version_problem else ""
        out(f"  {candidate.path.name}: {candidate.version} [{candidate.version_source}]{note}")
    if not assume_yes and prompt("Confirm these versions? [Y/n] ").strip().lower() in ("n", "no"):
        raise InitError("Version resolution not confirmed. Nothing written.")

    # Sorted by version so changelog drafts diff against the right predecessor and the live spec
    # is written from the newest graph rather than the union.
    ontology_candidates = [c for c in candidates if c.kind is discover.ContentKind.ONTOLOGY]
    ontology_candidates.sort(key=lambda c: version_key(c.version or ""))
    if not ontology_candidates:
        raise InitError("No owl:Ontology subject found across the discovered files.")
    refuse_duplicate_versions(ontology_candidates)
    selected = ontology_candidates[-1]

    ontology_iri = next(ontology_graph.subjects(RDF.type, OWL.Ontology), None)
    if not isinstance(ontology_iri, URIRef):
        raise InitError("No owl:Ontology subject found across the discovered files.")

    namespace_uri = envwrite.preferred_namespace_uri(ontology_graph, ontology_iri)
    if not namespace_uri:
        raise InitError("No vann:preferredNamespaceUri on the owl:Ontology node — cannot derive MODULE_NAMESPACE.")

    # From the selected graph, not the union: dcterms:title is multi-valued across versions.
    title = _dcterms_title(selected.graph, ontology_iri)

    # Drift check: disagreement on namespace across versions.
    namespaces = {
        envwrite.preferred_namespace_uri(c.graph, subject)
        for c in candidates
        if c.kind is discover.ContentKind.ONTOLOGY
        for subject in discover.ontology_subjects(c.graph)
    }
    namespaces.discard(None)
    if len(namespaces) > 1:
        raise InitError(f"Conflicting namespaces across discovered files: {sorted(str(n) for n in namespaces)}")

    slug_result = envwrite.derive_slug(namespace_uri, title, module_dir.name)
    resolved_slug = slug or slug_result.slug
    if slug_result.folder_mismatch and slug is None:
        warn(
            f"derived MODULE_SLUG={slug_result.slug!r} (from {slug_result.source}) "
            f"disagrees with the folder name {module_dir.name!r}."
        )
        if not assume_yes:
            answer = prompt(f"Use {slug_result.slug!r} anyway? [Y/n/<slug>] ").strip()
            if answer and answer.lower() not in ("y", "yes"):
                resolved_slug = answer

    default_authority = envwrite.w3id_authority_default(namespace_uri)
    resolved_authority = w3id_authority or default_authority
    if resolved_authority is None and not assume_yes:
        resolved_authority = prompt("W3ID_AUTHORITY (permanent-identifier authority): ").strip()
    if not resolved_authority:
        raise InitError("W3ID_AUTHORITY could not be derived and none was given.")

    # The w3id authority and the GitHub owner need not match, so it is an editable default.
    if repo_owner:
        resolved_owner = repo_owner
    elif assume_yes:
        resolved_owner = resolved_authority
    else:
        answer = prompt(f"REPO_OWNER (GitHub owner) [{resolved_authority}]: ").strip()
        resolved_owner = answer or resolved_authority
    if not resolved_owner:
        raise InitError("REPO_OWNER could not be derived and none was given.")

    env_path = module_dir / ".env"
    if env_path.exists() and not force:
        raise InitError(f"{env_path} already exists (use --force to overwrite).")

    env_values = envwrite.build_env(
        module_namespace=namespace_uri,
        slug=resolved_slug,
        repo_owner=resolved_owner,
        w3id_authority=resolved_authority,
    )

    spec_dir = module_dir / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    ontology_target = spec_dir / f"{resolved_slug}.ttl"
    shapes_target = spec_dir / f"{resolved_slug}.shacl.ttl"

    plan_lines = [
        f"  write {env_path.relative_to(module_dir)}",
        f"  write {ontology_target.relative_to(module_dir)} (from {selected.path.name}, v{selected.version})",
    ]
    if len(shapes_graph) > 0:
        plan_lines.append(f"  write {shapes_target.relative_to(module_dir)}")
    imported_versions = [c.version for c in ontology_candidates if c.source in ("from", "static-pin")]
    for version in imported_versions:
        plan_lines.append(
            f"  register pin v{version} (RDF-only: no reference.mdx/doc version is generated for imported history)"
        )
    out("Plan:")
    for line in plan_lines:
        out(line)
    if not assume_yes and prompt("Proceed? [Y/n] ").strip().lower() in ("n", "no"):
        raise InitError("Plan not confirmed. Nothing written.")

    envwrite.write_env(module_dir, env_values, force=force)
    # The highest version's own graph, never the union. See docs/adrs/ADR-004.
    write_generated(ontology_target, selected.graph.serialize(format="turtle"))
    (spec_dir / ".gitkeep").unlink(missing_ok=True)
    derived = [env_path, ontology_target]
    if len(shapes_graph) > 0:
        write_generated(shapes_target, shapes_graph.serialize(format="turtle"))
        derived.append(shapes_target)

    major_iri = f"https://w3id.org/{resolved_authority}/{resolved_slug}/v0/ont"

    changelog_dir = module_dir / "changelog"
    changelog_dir.mkdir(parents=True, exist_ok=True)

    # Imported history is RDF only: no reference.mdx, no doc version. See docs/adrs/ADR-003.
    static_dir = module_dir / "website" / "static"
    prior_pin_iri: URIRef | None = None
    for candidate in ontology_candidates:
        if candidate.source not in ("from", "static-pin"):
            continue
        pin_dir = static_dir / f"v{candidate.version}"
        if pin_dir.exists() and not force:
            warn(f"{pin_dir} already exists — leaving it alone (pass --force to overwrite).")
            continue
        cand_ontology_iri = next(candidate.graph.subjects(RDF.type, OWL.Ontology), None)
        if not isinstance(cand_ontology_iri, URIRef):
            continue
        pin_iri = URIRef(major_iri.replace("/v0/ont", f"/v{candidate.version}/ont"))
        render_docs.stamp_version(candidate.graph, cand_ontology_iri, pin_iri, candidate.version or "", prior_pin_iri)
        render_docs.write_artifact_tree(pin_dir, candidate.graph, ledger_src=None)
        derived.append(pin_dir / "ont" / "ont.ttl")
        prior_pin_iri = pin_iri

    for index, candidate in enumerate(ontology_candidates):
        changelog_path = changelog_dir / f"v{candidate.version}.md"
        if changelog_path.exists():
            continue
        previous = ontology_candidates[index - 1].graph if index > 0 else Graph()
        bullets = (
            render_site_data.diff_bullets(previous, candidate.graph, _ModuleStub())
            if index > 0
            else [f"Initial release of {title or resolved_slug}."]
        )
        write_generated(changelog_path, render_site_data.changelog_draft_text(candidate.version or "", None, bullets))
        derived.append(changelog_path)
    (changelog_dir / ".gitkeep").unlink(missing_ok=True)

    write_manifest(module_dir, derived)

    notes = bootstrap.finish_setup(module_dir, skip_install=skip_install)
    for note in notes:
        out(note)

    report.update(
        {
            "env": str(env_path.relative_to(module_dir)),
            "spec": str(ontology_target.relative_to(module_dir)),
            "spec_source": selected.path.name,
            "spec_version": selected.version,
            "slug": resolved_slug,
            "imported_versions": imported_versions,
        }
    )
    return report


def _dcterms_title(graph: Graph, ontology_iri: URIRef) -> str:
    values = [str(o) for o in graph.objects(ontology_iri, DCTERMS.title) if isinstance(o, Literal)]
    return values[0] if values else local_name(str(ontology_iri))


class _ModuleStub:
    """Just enough of render_site_data.ModuleData for diff_bullets, before any .env exists."""

    def is_internal(self, iri: str) -> bool:
        return True


def run(args: argparse.Namespace) -> int:
    try:
        run_init(
            Path(args.module_dir),
            from_dir=Path(args.from_dir) if args.from_dir else None,
            force=args.force,
            do_clean=args.clean,
            skip_install=args.skip_install,
            assume_yes=args.yes,
            repo_owner=args.repo_owner,
            w3id_authority=args.w3id_authority,
            slug=args.slug,
        )
    except InitError as exc:
        print(f"rdl-tools init: {exc}", file=sys.stderr)
        return 1
    # Reached when stdin cannot answer a prompt; say what to pass rather than raise EOFError.
    except EOFError:
        print(NO_INPUT, file=sys.stderr)
        return 2
    return 0
