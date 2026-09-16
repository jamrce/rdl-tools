"""The two allow-lists of ADR-004, and the live spec's provenance.

fixtures/companion-instance-data.ttl is the realistic case both rules exist to catch: instance
data with no `owl:Ontology` and no `sh:NodeShape`, which trips no other gate on its own.
"""

from __future__ import annotations

import io
import shutil
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from rdflib import DCTERMS, OWL, RDF, Graph, URIRef
from rdflib.compare import isomorphic

from rdl_tools import discover, spec
from rdl_tools.cli import main
from rdl_tools.commands.init import InitError, run_init

FIXTURES = Path(__file__).resolve().parent / "fixtures"
COMPANION = FIXTURES / "companion-instance-data.ttl"
SAMPLE_ONT = FIXTURES / "sample-ont"

PREFIXES = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix ex: <https://w3id.org/testauth/ex/v0/ont/> .
"""

ONTOLOGY = (
    PREFIXES
    + """
<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;
    dcterms:title "Example Module" ;
    owl:versionInfo "0.1.0" ;
    vann:preferredNamespaceUri "https://w3id.org/testauth/ex/v0/ont/" ;
    vann:preferredNamespacePrefix "ex" .

ex:Thing a owl:Class ;
    rdfs:label "Thing" .
"""
)

SHAPES = (
    PREFIXES
    + """
ex:ThingShape a sh:NodeShape ;
    sh:targetClass ex:Thing ;
    sh:property [ sh:path rdfs:label ; sh:minCount 1 ] .
"""
)

LEDGER = (
    PREFIXES
    + """
@prefix prov: <http://www.w3.org/ns/prov#> .
<https://w3id.org/testauth/ex/v0/ont#run-1> a prov:Activity .
"""
)


# the filename rule


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ex.ttl", spec.SpecKind.ONTOLOGY),
        ("two-words.ttl", spec.SpecKind.ONTOLOGY),
        ("ex.shacl.ttl", spec.SpecKind.SHAPES),
        ("ex.generated.ttl", spec.SpecKind.LEDGER),
        # None of these names a handler, so none of them reaches the published graph.
        ("ex.export.ttl", spec.SpecKind.UNSUPPORTED),
        ("ex.recognition.ttl", spec.SpecKind.UNSUPPORTED),
        ("ex.0.1.0.ttl", spec.SpecKind.UNSUPPORTED),
        (".hidden.ttl", spec.SpecKind.UNSUPPORTED),
        ("notes.md", spec.SpecKind.UNSUPPORTED),
        ("ttl", spec.SpecKind.UNSUPPORTED),
        (".ttl", spec.SpecKind.UNSUPPORTED),
    ],
)
def test_the_rule_is_an_allow_list_on_the_trailing_suffix(name: str, expected: spec.SpecKind):
    assert spec.classify_spec_file(Path("spec") / name) is expected


def test_a_deeper_compound_still_keys_off_the_trailing_two_parts():
    assert spec.classify_spec_file(Path("ex.core.shacl.ttl")) is spec.SpecKind.SHAPES
    assert spec.classify_spec_file(Path("ex.core.export.ttl")) is spec.SpecKind.UNSUPPORTED


def test_the_partition_of_a_directory_is_total(tmp_path: Path):
    for name, text in (
        ("ex.ttl", ONTOLOGY),
        ("ex.shacl.ttl", SHAPES),
        ("ex.generated.ttl", LEDGER),
        ("ex.export.ttl", COMPANION.read_text(encoding="utf-8")),
    ):
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert [p.name for p in spec.ontology_files(tmp_path)] == ["ex.ttl"]
    assert [p.name for p in spec.shape_files(tmp_path)] == ["ex.shacl.ttl"]
    assert [p.name for p in spec.ledger_files(tmp_path)] == ["ex.generated.ttl"]
    assert [p.name for p in spec.unsupported_files(tmp_path)] == ["ex.export.ttl"]


def test_the_hint_names_every_supported_name_and_no_other():
    hint = spec.supported_names_hint()
    assert "<stem>.ttl" in hint
    for suffix in spec.SUPPORTED_COMPOUND_SUFFIXES:
        assert f"<stem>.{suffix}" in hint
    assert "export" not in hint


# every entry point that scans spec/ refuses an unsupported file, exit 2, by name


@pytest.fixture
def module_root(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    (spec_dir / "ex.shacl.ttl").write_text(SHAPES, encoding="utf-8")
    return tmp_path


@pytest.fixture
def add_companion(module_root: Path):
    def add() -> Path:
        target = module_root / "spec" / "ex.export.ttl"
        shutil.copyfile(COMPANION, target)
        return target

    return add


def assert_refused_by_name(call, capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        call()
    assert raised.value.code == 2
    err = capsys.readouterr().err
    assert "ex.export.ttl" in err
    assert "<stem>.shacl.ttl" in err


def test_merge_ontology_refuses(module_root: Path, add_companion, capsys):
    add_companion()
    assert_refused_by_name(lambda: spec.merge_ontology(module_root / "spec"), capsys)


def test_merge_shapes_refuses(module_root: Path, add_companion, capsys):
    add_companion()
    assert_refused_by_name(lambda: spec.merge_shapes(module_root / "spec"), capsys)


def test_validate_refuses(module_root: Path, add_companion, capsys):
    add_companion()
    assert_refused_by_name(lambda: main(["validate", "--spec-dir", str(module_root / "spec")]), capsys)


def test_format_refuses_the_directory_and_the_named_file(module_root: Path, add_companion, capsys):
    companion = add_companion()
    assert_refused_by_name(lambda: main(["format", "--spec-dir", str(module_root / "spec")]), capsys)
    assert main(["format", "--ontology", str(companion)]) == 2
    assert "ex.export.ttl" in capsys.readouterr().err


def test_format_refuses_the_generated_ledger_by_name(module_root: Path, capsys):
    ledger = module_root / "spec" / "ex.generated.ttl"
    ledger.write_text(LEDGER, encoding="utf-8")
    assert main(["format", "--ontology", str(ledger)]) == 2
    assert "ex.generated.ttl" in capsys.readouterr().err
    assert ledger.read_text(encoding="utf-8") == LEDGER


def test_render_docs_refuses(module_root: Path, add_companion, capsys):
    add_companion()
    assert_refused_by_name(
        lambda: main(["render-docs", "--module-dir", str(module_root), "--version", "0.1.0"]), capsys
    )
    assert not (module_root / "website" / "static").exists(), "nothing may be written before the refusal"


def test_render_site_data_refuses(module_root: Path, capsys):
    module_dir = module_root / "sample-ont"
    shutil.copytree(SAMPLE_ONT, module_dir)
    shutil.copyfile(COMPANION, module_dir / "spec" / "sample-ont.export.ttl")
    with pytest.raises(SystemExit) as raised:
        main(["render-site-data", "--module-dir", str(module_dir), "--version", "0.5.7"])
    assert raised.value.code == 2
    assert "sample-ont.export.ttl" in capsys.readouterr().err


def test_the_merged_ontology_is_unchanged_by_a_refused_companion(module_root: Path, add_companion):
    spec_dir = module_root / "spec"
    clean = spec.merge_ontology(spec_dir)
    companion = add_companion()
    with pytest.raises(SystemExit):
        spec.merge_ontology(spec_dir)
    companion.unlink()

    assert isomorphic(clean, spec.merge_ontology(spec_dir))
    assert "example.net" not in clean.serialize(format="turtle")


def test_a_published_pin_survives_a_forced_rerun_byte_for_byte(module_root: Path, add_companion):
    pin = module_root / "website" / "static" / "v0.1.0" / "ont" / "ont.ttl"
    assert main(["render-docs", "--module-dir", str(module_root), "--version", "0.1.0"]) == 0
    before = pin.read_bytes()

    add_companion()
    with pytest.raises(SystemExit) as raised:
        main(["render-docs", "--module-dir", str(module_root), "--version", "0.1.0", "--force"])
    assert raised.value.code == 2
    assert pin.read_bytes() == before


def test_supported_names_keep_working(module_root: Path):
    (module_root / "spec" / "ex.generated.ttl").write_text(LEDGER, encoding="utf-8")
    assert main(["render-docs", "--module-dir", str(module_root), "--version", "0.1.0"]) == 0

    pin = module_root / "website" / "static" / "v0.1.0" / "ont"
    assert (pin / "ont.ttl").exists()
    assert (pin / "ledger.ttl").exists(), "the ledger is still copied in by name"
    graph = Graph()
    graph.parse(pin / "ont.ttl", format="turtle")
    assert (URIRef("https://w3id.org/testauth/ex/v0/ont/Thing"), RDF.type, OWL.Class) in graph
    # Shapes are validated, not published inside the ontology graph.
    assert "sh:NodeShape" not in (pin / "ont.ttl").read_text(encoding="utf-8")


def test_a_plain_stem_ttl_alongside_the_module_ontology_is_unaffected(module_root: Path):
    (module_root / "spec" / "imports.ttl").write_text(
        PREFIXES + '\nex:Extra a owl:Class ; rdfs:label "Extra" .\n', encoding="utf-8"
    )
    graph = spec.merge_ontology(module_root / "spec")
    assert (URIRef("https://w3id.org/testauth/ex/v0/ont/Extra"), RDF.type, OWL.Class) in graph


# the content rule


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A folder that counts as a module checkout, as `init` requires."""
    target = tmp_path / "ex"
    for folder in ("website", "changelog", "spec"):
        (target / folder).mkdir(parents=True)
    (target / "requirements.txt").write_text("rdl-tools==0.0.0\n", encoding="utf-8")
    return target


def init(module_dir: Path, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("assume_yes", True)
    kwargs.setdefault("skip_install", True)
    kwargs.setdefault("repo_owner", "owner")
    out = io.StringIO()
    with redirect_stdout(out):
        report = run_init(module_dir, out=lambda *a: print(*a, file=out), **kwargs)
    report["_stdout"] = out.getvalue()
    return report


def write_from_dir(tmp_path: Path, **files: str) -> Path:
    """A --from directory. `__` in a keyword spells `.`, so `ex__0__1__0__ttl` is `ex.0.1.0.ttl`."""
    directory = tmp_path / "history"
    directory.mkdir(exist_ok=True)
    for name, text in files.items():
        (directory / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return directory


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (ONTOLOGY, discover.ContentKind.ONTOLOGY),
        (SHAPES, discover.ContentKind.SHAPES),
        (COMPANION.read_text(encoding="utf-8"), discover.ContentKind.UNSUPPORTED),
        # A file carrying both is shapes; validate's gate 2 refuses shapes in an ontology file.
        (ONTOLOGY + SHAPES, discover.ContentKind.SHAPES),
    ],
)
def test_content_classification_is_three_way(text: str, expected: discover.ContentKind):
    graph = Graph()
    graph.parse(data=text, format="turtle")
    assert discover.classify_content(graph) is expected


def test_a_companion_at_the_module_root_is_refused_by_name_and_left_where_it_was(checkout: Path, capsys):
    (checkout / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    companion = checkout / "ex-export.ttl"
    shutil.copyfile(COMPANION, companion)
    before = companion.read_bytes()

    with pytest.raises(SystemExit) as raised:
        init(checkout)
    assert raised.value.code == 2
    err = capsys.readouterr().err
    assert "ex-export.ttl" in err
    assert "owl:Ontology" in err

    assert companion.exists(), "init never moves a file it refuses"
    assert companion.read_bytes() == before
    assert not (checkout / "spec" / "ex.ttl").exists(), "nothing is adopted after a refusal"
    assert not (checkout / ".env").exists()
    assert not (checkout / ".rdl-tools-manifest.json").exists()


def test_a_companion_in_the_from_directory_is_refused_too(checkout: Path, tmp_path: Path, capsys):
    (checkout / "ex.ttl").write_text(ONTOLOGY, encoding="utf-8")
    from_dir = write_from_dir(tmp_path, ex__export__ttl=COMPANION.read_text(encoding="utf-8"))
    with pytest.raises(SystemExit) as raised:
        init(checkout, from_dir=from_dir)
    assert raised.value.code == 2
    assert "ex.export.ttl" in capsys.readouterr().err


def test_a_dumped_version_filename_still_imports_and_resolves_from_the_filename(checkout: Path, tmp_path: Path):
    # `ex.0.1.0.ttl` trails as `0.ttl`, so the spec/ filename rule must not reach the import paths.
    no_version = ONTOLOGY.replace('    owl:versionInfo "0.1.0" ;\n', "")
    report = init(checkout, from_dir=write_from_dir(tmp_path, ex__0__1__0__ttl=no_version))
    assert report["imported_versions"] == ["0.1.0"]
    assert report["spec_source"] == "ex.0.1.0.ttl"
    assert "[filename]" in report["_stdout"]
    assert (checkout / "website" / "static" / "v0.1.0" / "ont" / "ont.ttl").exists()


# the live spec


def versioned(version: str, *, title: str, terms: tuple[str, ...], modified: str = "2026-01-01") -> str:
    body = "".join(f'ex:{term} a owl:Class ;\n    rdfs:label "{term}" .\n' for term in terms)
    return (
        PREFIXES
        + f"""
<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;
    dcterms:title "{title}" ;
    dcterms:modified "{modified}" ;
    owl:versionInfo "{version}" ;
    vann:preferredNamespaceUri "https://w3id.org/testauth/ex/v0/ont/" ;
    vann:preferredNamespacePrefix "ex" .

"""
        + body
    )


THING = URIRef("https://w3id.org/testauth/ex/v0/ont/Thing")
RETIRED = URIRef("https://w3id.org/testauth/ex/v0/ont/Retired")
THIRD = URIRef("https://w3id.org/testauth/ex/v0/ont/Third")
ONTOLOGY_IRI = URIRef("https://w3id.org/testauth/ex/v0/ont")


@pytest.fixture
def history(tmp_path: Path) -> Path:
    """A non-additive history: 0.2.0 retires a term 0.1.0 had. A union would resurrect it."""
    return write_from_dir(
        tmp_path,
        ex__0__1__0__ttl=versioned("0.1.0", title="Example One", terms=("Thing", "Retired"), modified="2026-01-01"),
        ex__0__2__0__ttl=versioned("0.2.0", title="Example Two", terms=("Thing",), modified="2026-02-01"),
        ex__1__0__0__ttl=versioned("1.0.0", title="Example Three", terms=("Thing", "Third"), modified="2026-03-01"),
    )


def parse(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def pin_graph(checkout: Path, version: str) -> Graph:
    return parse(checkout / "website" / "static" / f"v{version}" / "ont" / "ont.ttl")


def test_the_live_spec_is_the_newest_graph_not_the_union(checkout: Path, history: Path):
    report = init(checkout, from_dir=history)
    assert (report["spec_version"], report["spec_source"]) == ("1.0.0", "ex.1.0.0.ttl")

    graph = parse(checkout / "spec" / "ex.ttl")
    assert (THING, RDF.type, OWL.Class) in graph
    assert (THIRD, RDF.type, OWL.Class) in graph
    assert (RETIRED, RDF.type, OWL.Class) not in graph
    assert isomorphic(graph, parse(history / "ex.1.0.0.ttl")), "the live spec is the newest input graph, unaltered"


@pytest.mark.parametrize(
    ("predicate", "expected"),
    [(OWL.versionInfo, "1.0.0"), (DCTERMS.title, "Example Three"), (DCTERMS.modified, "2026-03-01")],
)
def test_the_single_subject_metadata_stays_single_valued(
    checkout: Path, history: Path, predicate: URIRef, expected: str
):
    init(checkout, from_dir=history)
    graph = parse(checkout / "spec" / "ex.ttl")
    assert sorted(str(o) for o in graph.objects(ONTOLOGY_IRI, predicate)) == [expected]


def test_the_highest_version_wins_over_discovery_order(checkout: Path, history: Path):
    # 1.0.0 sorts above 0.2.0 numerically, not lexically, and the newest file is not the last
    # one discovered by name.
    assert init(checkout, from_dir=history)["spec_version"] == "1.0.0"


def test_each_pin_carries_its_own_graph(checkout: Path, history: Path):
    init(checkout, from_dir=history)

    first = pin_graph(checkout, "0.1.0")
    assert (RETIRED, RDF.type, OWL.Class) in first, "a pin holds the version it was cut from"
    assert (THIRD, RDF.type, OWL.Class) not in first
    assert (RETIRED, RDF.type, OWL.Class) not in pin_graph(checkout, "0.2.0")
    assert (THIRD, RDF.type, OWL.Class) in pin_graph(checkout, "1.0.0")


@pytest.mark.parametrize(("version", "prior"), [("0.2.0", "0.1.0"), ("1.0.0", "0.2.0")])
def test_each_pin_chains_the_prior_version(checkout: Path, history: Path, version: str, prior: str):
    init(checkout, from_dir=history)
    graph = pin_graph(checkout, version)
    assert str(next(graph.objects(ONTOLOGY_IRI, OWL.priorVersion))) == f"https://w3id.org/testauth/ex/v{prior}/ont"
    assert str(next(graph.objects(ONTOLOGY_IRI, OWL.versionInfo))) == version


def test_the_oldest_pin_has_no_prior_version(checkout: Path, history: Path):
    init(checkout, from_dir=history)
    assert next(pin_graph(checkout, "0.1.0").objects(ONTOLOGY_IRI, OWL.priorVersion), None) is None


def test_the_changelog_reports_the_removal_against_the_right_predecessor(checkout: Path, history: Path):
    init(checkout, from_dir=history)
    assert "Removed class `Retired`" in (checkout / "changelog" / "v0.2.0.md").read_text(encoding="utf-8")
    third = (checkout / "changelog" / "v1.0.0.md").read_text(encoding="utf-8")
    assert "Added class `Third`" in third
    assert "Retired" not in third


def test_two_files_resolving_to_one_version_are_refused_by_name(checkout: Path, tmp_path: Path):
    from_dir = write_from_dir(
        tmp_path,
        first__ttl=versioned("0.1.0", title="Example One", terms=("Thing",)),
        second__ttl=versioned("0.1.0", title="Example One", terms=("Other",)),
    )
    with pytest.raises(InitError) as raised:
        init(checkout, from_dir=from_dir)
    message = str(raised.value)
    assert "0.1.0" in message
    assert "first.ttl" in message
    assert "second.ttl" in message
    assert not (checkout / "spec" / "ex.ttl").exists()
