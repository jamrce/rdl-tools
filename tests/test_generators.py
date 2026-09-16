"""`format`, `expand-pins`, `render-docs` and `fetch-fonts` — the generators without a fixture
module of their own.

Each builds the smallest tree that exercises its contract, so a failure names one behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import OWL, Graph, URIRef

from rdl_tools.cli import main
from rdl_tools.commands import fetch_fonts
from rdl_tools.commands.fmt import normalize_turtle

ONTOLOGY = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <https://w3id.org/testauth/ex/v0/ont/> .

<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology .
ex:Thing a owl:Class ; rdfs:label "Thing" .
"""

# Deliberately ugly: one long line, non-canonical prefix order, an unused prefix.
UNFORMATTED = (
    "@prefix unused: <https://example.org/unused/> .\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "@prefix ex: <https://w3id.org/testauth/ex/v0/ont/> .\n"
    "<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology . ex:Thing a owl:Class .\n"
)


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    return spec


# format


def test_format_rewrites_then_reports_up_to_date(tmp_path: Path):
    spec = tmp_path / "spec"
    spec.mkdir()
    target = spec / "ex.ttl"
    target.write_text(UNFORMATTED, encoding="utf-8")

    assert main(["format", "--spec-dir", str(spec)]) == 0
    once = target.read_text(encoding="utf-8")
    assert main(["format", "--spec-dir", str(spec)]) == 0
    assert target.read_text(encoding="utf-8") == once
    assert main(["format", "--check", "--spec-dir", str(spec)]) == 0


def test_format_is_idempotent(tmp_path: Path):
    # The property the whole point of the command rests on: format(format(x)) == format(x).
    target = tmp_path / "ex.ttl"
    target.write_text(UNFORMATTED, encoding="utf-8")
    once = normalize_turtle(target)
    target.write_text(once, encoding="utf-8")
    assert normalize_turtle(target) == once


def test_format_check_fails_on_unformatted_input_and_writes_nothing(tmp_path: Path):
    spec = tmp_path / "spec"
    spec.mkdir()
    target = spec / "ex.ttl"
    target.write_text(UNFORMATTED, encoding="utf-8")
    assert main(["format", "--check", "--spec-dir", str(spec)]) == 1
    assert target.read_text(encoding="utf-8") == UNFORMATTED


def test_format_never_touches_a_published_pin(tmp_path: Path):
    pin = tmp_path / "website" / "static" / "v0.1.0" / "ont"
    pin.mkdir(parents=True)
    target = pin / "ont.ttl"
    target.write_text(UNFORMATTED, encoding="utf-8")
    assert main(["format", "--ontology", str(target)]) == 2
    assert target.read_text(encoding="utf-8") == UNFORMATTED


def test_format_skips_shapes_and_ledger_files(tmp_path: Path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    (spec / "ex.shacl.ttl").write_text(UNFORMATTED, encoding="utf-8")
    (spec / "ex.generated.ttl").write_text(UNFORMATTED, encoding="utf-8")
    assert main(["format", "--spec-dir", str(spec)]) == 0
    # Only the ontology file was canonicalised; the shapes and the ledger are untouched.
    assert main(["format", "--check", "--spec-dir", str(spec)]) == 0
    assert (spec / "ex.shacl.ttl").read_text(encoding="utf-8") == UNFORMATTED
    assert (spec / "ex.generated.ttl").read_text(encoding="utf-8") == UNFORMATTED


def test_format_reports_missing_inputs(tmp_path: Path):
    assert main(["format", "--ontology", str(tmp_path / "nope.ttl")]) == 2
    assert main(["format", "--spec-dir", str(tmp_path / "nope")]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["format", "--spec-dir", str(empty)]) == 2


# render-docs


def _module(tmp_path: Path) -> Path:
    module_dir = tmp_path / "ex"
    (module_dir / "spec").mkdir(parents=True)
    (module_dir / "spec" / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    return module_dir


def test_render_docs_writes_the_pin_and_the_v0_copy(tmp_path: Path):
    module_dir = _module(tmp_path)
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    static = module_dir / "website" / "static"
    for name in ("ont.ttl", "ont.rdf", "ont.jsonld", "ont.nt"):
        assert (static / "v0.1.0" / "ont" / name).exists()
        assert (static / "v0" / "ont" / name).exists()

    graph = Graph()
    graph.parse(static / "v0.1.0" / "ont" / "ont.ttl", format="turtle")
    subject = URIRef("https://w3id.org/testauth/ex/v0/ont")
    assert graph.value(subject, OWL.versionIRI) == URIRef("https://w3id.org/testauth/ex/v0.1.0/ont")
    assert str(graph.value(subject, OWL.versionInfo)) == "0.1.0"


def test_render_docs_refuses_to_overwrite_a_pin_without_force(tmp_path: Path):
    module_dir = _module(tmp_path)
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 1
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0", "--force"]) == 0


def test_render_docs_chains_prior_version(tmp_path: Path):
    module_dir = _module(tmp_path)
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.2.0"]) == 0
    graph = Graph()
    graph.parse(module_dir / "website" / "static" / "v0.2.0" / "ont" / "ont.ttl", format="turtle")
    prior = graph.value(URIRef("https://w3id.org/testauth/ex/v0/ont"), OWL.priorVersion)
    assert str(prior) == "https://w3id.org/testauth/ex/v0.1.0/ont"


def test_render_docs_copies_a_generated_ledger_into_every_tree(tmp_path: Path):
    module_dir = _module(tmp_path)
    (module_dir / "spec" / "ex.generated.ttl").write_text("# ledger\n", encoding="utf-8")
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    static = module_dir / "website" / "static"
    assert (static / "v0.1.0" / "ont" / "ledger.ttl").read_text(encoding="utf-8") == "# ledger\n"
    assert (static / "v0" / "ont" / "ledger.ttl").exists()


def test_render_docs_refuses_an_ontology_iri_off_the_url_contract(tmp_path: Path):
    module_dir = tmp_path / "ex"
    (module_dir / "spec").mkdir(parents=True)
    (module_dir / "spec" / "ex.ttl").write_text(
        ONTOLOGY.replace("https://w3id.org/testauth/ex/v0/ont>", "https://example.org/flat>"),
        encoding="utf-8",
    )
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 2


# expand-pins


def test_expand_pins_rebuilds_the_derived_files_and_v0(tmp_path: Path):
    module_dir = _module(tmp_path)
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.2.0"]) == 0

    static = module_dir / "website" / "static"
    # Simulate a fresh clone: only each pin's ont.ttl is committed.
    for pin in ("v0.1.0", "v0.2.0"):
        for name in ("ont.rdf", "ont.jsonld", "ont.nt"):
            (static / pin / "ont" / name).unlink()
    import shutil

    shutil.rmtree(static / "v0")

    assert main(["expand-pins", "--module-dir", str(module_dir)]) == 0
    for pin in ("v0.1.0", "v0.2.0"):
        for name in ("ont.rdf", "ont.jsonld", "ont.nt"):
            assert (static / pin / "ont" / name).exists()
    # v0 is a copy of the newest pin, not a merge.
    v0 = Graph()
    v0.parse(static / "v0" / "ont" / "ont.ttl", format="turtle")
    assert v0.value(URIRef("https://w3id.org/testauth/ex/v0/ont"), OWL.versionInfo) is not None
    assert str(v0.value(URIRef("https://w3id.org/testauth/ex/v0/ont"), OWL.versionInfo)) == "0.2.0"


def test_expand_pins_is_a_no_op_before_the_first_release(tmp_path: Path, capsys):
    module_dir = _module(tmp_path)
    assert main(["expand-pins", "--module-dir", str(module_dir)]) == 0
    assert "nothing to expand" in capsys.readouterr().out


def test_expand_pins_is_idempotent(tmp_path: Path):
    module_dir = _module(tmp_path)
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert main(["expand-pins", "--module-dir", str(module_dir)]) == 0
    once = (module_dir / "website" / "static" / "v0" / "ont" / "ont.nt").read_bytes()
    assert main(["expand-pins", "--module-dir", str(module_dir)]) == 0
    assert (module_dir / "website" / "static" / "v0" / "ont" / "ont.nt").read_bytes() == once


# fetch-fonts

CSS2_RESPONSE = """/* cyrillic */
@font-face {
  font-family: 'Barlow';
  font-style: normal;
  font-weight: 400;
  src: url(https://fonts.gstatic.com/s/barlow/cyr.woff2) format('woff2');
  unicode-range: U+0301, U+0400-045F;
}
/* latin-ext */
@font-face {
  font-family: 'Barlow';
  font-style: normal;
  font-weight: 400;
  src: url(https://fonts.gstatic.com/s/barlow/latinext.woff2) format('woff2');
  unicode-range: U+0100-02AF;
}
/* latin */
@font-face {
  font-family: 'Barlow Condensed';
  font-style: normal;
  font-weight: 700;
  src: url(https://fonts.gstatic.com/s/barlowcondensed/latin.woff2) format('woff2');
  unicode-range: U+0000-00FF;
}
"""


def test_only_the_wanted_subsets_are_kept():
    faces = list(fetch_fonts.parse_faces(CSS2_RESPONSE))
    assert [(f[0], f[1], f[2]) for f in faces] == [
        ("Barlow", "400", "latin-ext"),
        ("Barlow Condensed", "700", "latin"),
    ]


def test_emitted_css_is_self_hosted_and_deterministic():
    faces = list(fetch_fonts.parse_faces(CSS2_RESPONSE))
    css = fetch_fonts.fonts_css_text(faces)
    assert css == fetch_fonts.fonts_css_text(faces)
    assert "https://" not in css.split("*/", 1)[1]  # no third-party request survives
    assert "url('./fonts/barlow-400-latin-ext.woff2')" in css
    assert "url('./fonts/barlow-condensed-700-latin.woff2')" in css
    assert "unicode-range: U+0100-02AF;" in css


def test_a_malformed_block_is_skipped_rather_than_half_written():
    broken = "/* latin */\n@font-face {\n  font-family: 'Barlow';\n}\n"
    assert list(fetch_fonts.parse_faces(broken)) == []


def test_fetching_from_an_unexpected_host_is_refused():
    with pytest.raises(ValueError, match="refusing to fetch"):
        fetch_fonts.fetch("https://example.com/evil.woff2")


@pytest.mark.network
def test_the_live_css2_api_still_returns_the_faces_we_parse():
    css = fetch_fonts.fetch(fetch_fonts.GOOGLE_CSS_URL, browser=True).decode("utf-8")
    faces = list(fetch_fonts.parse_faces(css))
    assert {f[0] for f in faces} == {"Barlow", "Barlow Condensed"}
    assert all(url.endswith(".woff2") for *_, url, _range in faces)
