"""End to end, from the built wheel, in a fresh environment.

Nothing here imports `rdl_tools` in-process; every step goes through the installed console entry
point, as a module's CI does. The module checkout is built in code rather than copied from
rdl-module-template — asserting that the real skeleton builds a real site is that repo's job.

The environment is built with uv, whose cache makes it near-instant and needs no network on a
warm machine. Plain `venv` + `pip` is covered by ci.yml's wheel smoke test instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import OWL, Graph, URIRef

FIXTURE_ONTOLOGY = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix ex: <https://w3id.org/testauth/e2e/v0/ont/> .

<https://w3id.org/testauth/e2e/v0/ont> a owl:Ontology ;
    dcterms:title "End To End Module" ;
    dcterms:description \"\"\"
        A module scaffolded, generated and built
        entirely from the published wheel.
        \"\"\" ;
    dcterms:license <https://spdx.org/licenses/MIT.html> ;
    dcterms:modified "2026-09-05" ;
    owl:versionInfo "0.1.0" ;
    vann:preferredNamespaceUri "https://w3id.org/testauth/e2e/v0/ont/" ;
    vann:preferredNamespacePrefix "ex" .

ex:Thing a owl:Class ;
    rdfs:label "Thing" ;
    skos:definition "Anything at all." .

ex:Widget a owl:Class ;
    rdfs:subClassOf ex:Thing ;
    rdfs:label "Widget" ;
    skos:definition "A thing that is a widget." .

ex:partOf a owl:ObjectProperty ;
    rdfs:domain ex:Widget ;
    rdfs:range ex:Thing ;
    rdfs:label "partOf" ;
    skos:definition "Relates a widget to the thing it belongs to." .
"""

FIXTURE_SHAPES = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://w3id.org/testauth/e2e/v0/ont/> .

ex:WidgetShape a sh:NodeShape ;
    sh:targetClass ex:Widget ;
    sh:property [ sh:path ex:partOf ; sh:class ex:Thing ; sh:maxCount 1 ] .
"""

# The files a release commits. `expand-pins` output is excluded: rdflib reorders on every
# serialisation, which is why only each pin's ont.ttl is committed.
DETERMINISTIC_PATHS = (
    ".env",
    "spec/e2e.ttl",
    "spec/e2e.shacl.ttl",
    "changelog/v0.1.0.md",
    "website/src/generated/site.json",
    "website/src/generated/releases.json",
    "website/src/generated/0.1.0.json",
    "website/src/generated/index.js",
    "website/docs/reference.mdx",
    "website/static/v0.1.0/ont/ont.ttl",
)


def _venv_bin(root: Path, name: str) -> Path:
    folder = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return root / folder / f"{name}{suffix}"


@pytest.fixture(scope="session")
def _clean_install(wheel: Path, tmp_path_factory: pytest.TempPathFactory) -> Path | str:
    """The console script from a fresh environment holding only the wheel, or why there is none.

    Returns a reason rather than skipping: a session fixture that skips during setup trips a
    pytest internal assertion when several tests request it.
    """
    if shutil.which("uv") is None:  # pragma: no cover - environment-dependent
        return "uv is not on PATH — see CONTRIBUTING.md"
    env_dir = tmp_path_factory.mktemp("venv") / "env"
    for argv in (
        # The interpreter running the suite, so the matrix tests the wheel on both 3.13 and 3.14.
        ["uv", "venv", "--python", sys.executable, str(env_dir)],
        ["uv", "pip", "install", "--python", str(_venv_bin(env_dir, "python")), "--quiet", str(wheel)],
    ):
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        if result.returncode != 0:  # pragma: no cover - environment-dependent
            return f"`{' '.join(argv[:2])}` failed (offline?):\n{result.stderr[-2000:]}"
    return _venv_bin(env_dir, "rdl-tools")


@pytest.fixture
def installed_cli(_clean_install: Path | str) -> Path:
    if isinstance(_clean_install, str):
        pytest.skip(_clean_install)
    return _clean_install


def cli(installed_cli: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(installed_cli), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    assert result.returncode == 0, f"rdl-tools {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result


def make_checkout(target: Path) -> None:
    """The least `init` accepts as a module repo, plus the ontology to derive from."""
    for folder in ("website", "github/workflows", "changelog", "spec"):
        (target / folder).mkdir(parents=True)
    (target / "requirements.txt").write_text("rdl-tools==0.0.0\n", encoding="utf-8")
    (target / "e2e.ttl").write_text(FIXTURE_ONTOLOGY, encoding="utf-8")
    (target / "e2e-shapes.ttl").write_text(FIXTURE_SHAPES, encoding="utf-8")


def configure_and_generate(installed_cli: Path, target: Path) -> None:
    """Configure a module checkout, then run every generator against the result."""
    make_checkout(target)

    cli(
        installed_cli,
        "init",
        "--module-dir",
        str(target),
        "--yes",
        "--skip-install",
        "--repo-owner",
        "testauth",
    )

    cli(installed_cli, "validate", "--spec-dir", "spec", cwd=target)
    cli(installed_cli, "format", "--check", "--spec-dir", "spec", cwd=target)
    cli(installed_cli, "render-docs", "--module-dir", ".", "--version", "0.1.0", cwd=target)
    cli(installed_cli, "render-site-data", "--module-dir", ".", "--version", "0.1.0", cwd=target)
    cli(installed_cli, "render-site-data", "--module-dir", ".", "--check", cwd=target)
    cli(installed_cli, "expand-pins", "--module-dir", ".", cwd=target)


@pytest.fixture(scope="module")
def _generated_tree(_clean_install: Path | str, tmp_path_factory: pytest.TempPathFactory) -> Path | str:
    """One configured-and-generated checkout shared by the tests that only read it, or why there is none."""
    if isinstance(_clean_install, str):
        return _clean_install
    target = tmp_path_factory.mktemp("generated") / "e2e"
    configure_and_generate(_clean_install, target)
    return target


@pytest.fixture
def generated_tree(_generated_tree: Path | str) -> Path:
    if isinstance(_generated_tree, str):
        pytest.skip(_generated_tree)
    return _generated_tree


def test_generated_files_carry_ontology_iris_on_the_url_contract(generated_tree: Path):
    payload = json.loads((generated_tree / "website" / "src" / "generated" / "0.1.0.json").read_text(encoding="utf-8"))
    ontology = payload["ontology"]
    iri, version_iri, namespace = ontology["iri"], ontology["versionIri"], ontology["namespace"]["uri"]

    for document_iri in (iri, version_iri):
        assert document_iri.startswith("https://"), document_iri
        assert not document_iri.endswith("/"), document_iri
    assert namespace.startswith("https://"), namespace
    assert namespace.endswith("/"), namespace

    assert version_iri == iri.replace("/v0/ont", "/v0.1.0/ont")
    # versionIri comes from .env; the pin's owl:versionIRI comes from the .ttl. They must agree.
    pin = Graph().parse(generated_tree / "website" / "static" / "v0.1.0" / "ont" / "ont.ttl", format="turtle")
    assert [str(o) for o in pin.objects(URIRef(iri), OWL.versionIRI)] == [version_iri]


def test_generated_files_list_exactly_the_module_releases(generated_tree: Path):
    releases = json.loads(
        (generated_tree / "website" / "src" / "generated" / "releases.json").read_text(encoding="utf-8")
    )
    changelogs = {path.stem[1:] for path in (generated_tree / "changelog").glob("v*.md")}
    pins = {
        child.name[1:]
        for child in (generated_tree / "website" / "static").iterdir()
        if child.is_dir() and child.name != "v0"
    }

    ids = [release["id"] for release in releases]
    assert ids == ["0.1.0"]
    assert set(ids) == changelogs | pins


def test_site_title_and_tagline_are_single_line(generated_tree: Path):
    site = json.loads((generated_tree / "website" / "src" / "generated" / "site.json").read_text(encoding="utf-8"))
    assert site["title"] == "End To End Module"
    assert site["tagline"] == "A module scaffolded, generated and built entirely from the published wheel."


def test_the_configured_tree_is_what_a_module_repo_should_look_like(installed_cli: Path, tmp_path: Path):
    target = tmp_path / "e2e"
    configure_and_generate(installed_cli, target)

    # No build code reaches a module, ever.
    assert not (target / "scripts").exists()
    assert list(target.rglob("*.py")) == []
    # CI was activated: github/workflows/ became .github/workflows/.
    assert (target / ".github" / "workflows").is_dir()
    assert not (target / "github").exists()

    env_text = (target / ".env").read_text(encoding="utf-8")
    assert "MODULE_SLUG=e2e" in env_text
    assert "MODULE_NAMESPACE=https://w3id.org/testauth/e2e/v0/ont/" in env_text
    assert "W3ID_AUTHORITY=testauth" in env_text

    # The mis-named shapes file was classified by content and renamed.
    assert (target / "spec" / "e2e.shacl.ttl").exists()
    assert not (target / "e2e-shapes.ttl").exists()

    # Every generator's own output landed.
    for name in ("ont.ttl", "ont.rdf", "ont.jsonld", "ont.nt"):
        assert (target / "website" / "static" / "v0.1.0" / "ont" / name).exists()
        assert (target / "website" / "static" / "v0" / "ont" / name).exists()
    reference = (target / "website" / "docs" / "reference.mdx").read_text(encoding="utf-8")
    assert "### Widget {#Widget}" in reference
    assert "### partOf {#partOf}" in reference
    # render-docs ran first, so the Home page gets a download row.
    site_data = json.loads((target / "website" / "src" / "generated" / "0.1.0.json").read_text(encoding="utf-8"))
    assert site_data["downloads"]


def test_two_runs_produce_identical_committed_output(installed_cli: Path, tmp_path: Path):
    first, second = tmp_path / "a" / "e2e", tmp_path / "b" / "e2e"
    configure_and_generate(installed_cli, first)
    configure_and_generate(installed_cli, second)

    for relative in DETERMINISTIC_PATHS:
        left, right = first / relative, second / relative
        assert left.exists(), relative
        assert left.read_bytes() == right.read_bytes(), f"{relative} differs between runs"
