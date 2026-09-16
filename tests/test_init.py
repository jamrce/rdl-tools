"""Tests for `rdl-tools init`, against fixtures in a temp directory. No network, no subprocesses."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from rdflib import OWL, Graph

from rdl_tools import discover, envwrite
from rdl_tools.cli import main
from rdl_tools.commands.init import InitError, run_init

PREFIXES = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix ex: <https://w3id.org/testauth/ex/v0/ont/> .
"""


def ontology_ttl(version: str, *, title: str = "Example Module", extra: str = "") -> str:
    return (
        PREFIXES
        + f"""
<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;
    dcterms:title "{title}" ;
    owl:versionInfo "{version}" ;
    vann:preferredNamespaceUri "https://w3id.org/testauth/ex/v0/ont/" ;
    vann:preferredNamespacePrefix "ex" .

ex:Thing a owl:Class ;
    rdfs:label "Thing" .
{extra}
"""
    )


SHAPES_TTL = (
    PREFIXES
    + """
ex:ThingShape a sh:NodeShape ;
    sh:targetClass ex:Thing ;
    sh:property [ sh:path rdfs:label ; sh:minCount 1 ] .
"""
)


@pytest.fixture
def module_dir(tmp_path: Path) -> Path:
    """The least that counts as a module checkout; a real one comes from the template."""
    target = tmp_path / "ex"
    for folder in ("website", "github/workflows", "changelog", "spec"):
        (target / folder).mkdir(parents=True)
    (target / "requirements.txt").write_text("rdl-tools==0.0.0\n", encoding="utf-8")
    return target


def run(module_dir: Path, **kwargs: Any) -> dict[str, Any]:
    """run_init with --yes semantics, capturing progress output under `_stdout`."""
    kwargs.setdefault("assume_yes", True)
    kwargs.setdefault("skip_install", True)
    out = io.StringIO()
    with redirect_stdout(out):
        report = run_init(module_dir, out=lambda *a: print(*a, file=out), **kwargs)
    report["_stdout"] = out.getvalue()
    return report


# what counts as a module


def test_a_folder_that_is_not_a_module_checkout_is_refused(tmp_path: Path):
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(SystemExit) as raised:
        run(bare, repo_owner="owner")
    assert raised.value.code == 2


def test_no_build_code_is_ever_written_into_a_module(module_dir: Path):
    run(module_dir, repo_owner="owner")
    assert not (module_dir / "scripts").exists()
    assert list(module_dir.rglob("*.py")) == []


def test_workflows_are_activated_by_renaming_the_directory(module_dir: Path):
    # Their contents are the template's business; switching them on is this command's.
    (module_dir / "github" / "workflows" / "validate.yml").write_text("name: v\n", encoding="utf-8")
    run(module_dir, repo_owner="owner")
    assert (module_dir / ".github" / "workflows" / "validate.yml").exists()
    assert not (module_dir / "github").exists()


# a single loose root .ttl drives .env derivation


def test_single_root_ttl_derives_env_with_slug_from_namespace_segment(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    report = run(module_dir, repo_owner="owner")
    env_text = (module_dir / ".env").read_text(encoding="utf-8")
    assert "MODULE_SLUG=ex" in env_text
    assert "MODULE_NAMESPACE=https://w3id.org/testauth/ex/v0/ont/" in env_text
    assert "REPO_OWNER=owner" in env_text
    assert "W3ID_AUTHORITY=testauth" in env_text
    assert report["slug"] == "ex"
    assert "Example Module" in (module_dir / "spec" / "ex.ttl").read_text(encoding="utf-8")


def test_slug_derivation_prefers_namespace_over_title_and_folder():
    result = envwrite.derive_slug(
        "https://w3id.org/apollo-protocol/irm/v0/ont/",
        "Information Requirements Methodology",
        "irm",
    )
    assert (result.slug, result.source) == ("irm", "namespace")
    assert not result.folder_mismatch


def test_slug_derivation_warns_on_folder_mismatch():
    result = envwrite.derive_slug(
        "https://w3id.org/apollo-protocol/irm/v0/ont/", "Information Requirements Methodology", "other-folder"
    )
    assert result.slug == "irm"
    assert result.folder_mismatch


def test_slug_falls_back_to_title_then_folder():
    by_title = envwrite.derive_slug("https://example.org/no-version/", "Some Module", "folder")
    assert (by_title.slug, by_title.source) == ("some-module", "title")
    by_folder = envwrite.derive_slug("https://example.org/no-version/", "", "folder")
    assert (by_folder.slug, by_folder.source) == ("folder", "folder")


def test_an_explicit_slug_overrides_derivation(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    report = run(module_dir, repo_owner="owner", slug="chosen")
    assert report["slug"] == "chosen"
    assert (module_dir / "spec" / "chosen.ttl").exists()


# --from, with three or more versions


def test_from_directory_orders_diffs_and_registers_pins(module_dir: Path, tmp_path: Path):
    from_dir = tmp_path / "history"
    from_dir.mkdir()
    (from_dir / "ex-0.1.0.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    (from_dir / "ex-0.2.0.ttl").write_text(ontology_ttl("0.2.0", extra="ex:Other a owl:Class ."), encoding="utf-8")
    (from_dir / "ex-0.3.0.ttl").write_text(
        ontology_ttl("0.3.0", extra="ex:Other a owl:Class .\nex:Third a owl:Class ."),
        encoding="utf-8",
    )
    report = run(module_dir, from_dir=from_dir, repo_owner="owner")

    assert sorted(report["imported_versions"]) == ["0.1.0", "0.2.0", "0.3.0"]
    for version in ("0.1.0", "0.2.0", "0.3.0"):
        pin = module_dir / "website" / "static" / f"v{version}" / "ont" / "ont.ttl"
        assert pin.exists(), f"missing pin for {version}"
        assert not (pin.parent / "index.html").exists(), "imported pins stay RDF-only"
    assert "Added class `Other`" in (module_dir / "changelog" / "v0.2.0.md").read_text(encoding="utf-8")
    assert "Added class `Third`" in (module_dir / "changelog" / "v0.3.0.md").read_text(encoding="utf-8")


def test_imported_pins_chain_prior_version_links(module_dir: Path, tmp_path: Path):
    from_dir = tmp_path / "history"
    from_dir.mkdir()
    (from_dir / "ex-0.1.0.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    (from_dir / "ex-0.2.0.ttl").write_text(ontology_ttl("0.2.0"), encoding="utf-8")
    run(module_dir, from_dir=from_dir, repo_owner="owner")

    graph = Graph()
    graph.parse(module_dir / "website" / "static" / "v0.2.0" / "ont" / "ont.ttl", format="turtle")
    prior = next(graph.objects(None, OWL.priorVersion), None)
    assert str(prior) == "https://w3id.org/testauth/ex/v0.1.0/ont"


# refusals


def test_conflicting_namespace_across_files_aborts(module_dir: Path, tmp_path: Path):
    (module_dir / "a.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    from_dir = tmp_path / "history"
    from_dir.mkdir()
    conflicting = (
        PREFIXES.replace("https://w3id.org/testauth/ex/v0/ont/", "https://w3id.org/other/ex/v0/ont/")
        + """
<https://w3id.org/other/ex/v0/ont> a owl:Ontology ;
    dcterms:title "Example Module" ;
    owl:versionInfo "0.0.9" ;
    vann:preferredNamespaceUri "https://w3id.org/other/ex/v0/ont/" .
"""
    )
    (from_dir / "old.ttl").write_text(conflicting, encoding="utf-8")
    with pytest.raises(InitError):
        run(module_dir, from_dir=from_dir, repo_owner="owner")


def test_non_semver_version_label_is_normalised(module_dir: Path):
    (module_dir / "a.ttl").write_text(ontology_ttl("0.2.0 (RC2)"), encoding="utf-8")
    report = run(module_dir, repo_owner="owner")
    assert (module_dir / "changelog" / "v0.2.0.md").exists()
    assert "normalised" in report["_stdout"]


def test_unresolvable_version_is_refused_not_guessed(module_dir: Path):
    broken = (
        PREFIXES
        + """
<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;
    dcterms:title "Example Module" ;
    vann:preferredNamespaceUri "https://w3id.org/testauth/ex/v0/ont/" .
"""
    )
    (module_dir / "noversion.ttl").write_text(broken, encoding="utf-8")
    with pytest.raises(InitError):
        run(module_dir, repo_owner="owner")


def test_a_missing_preferred_namespace_is_refused(module_dir: Path):
    no_namespace = (
        PREFIXES
        + """
<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;
    dcterms:title "Example Module" ;
    owl:versionInfo "0.1.0" .
"""
    )
    (module_dir / "ex.ttl").write_text(no_namespace, encoding="utf-8")
    with pytest.raises(InitError):
        run(module_dir, repo_owner="owner")


def test_two_ontology_subjects_are_refused(module_dir: Path):
    (module_dir / "a.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    second = (
        PREFIXES
        + """
<https://w3id.org/testauth/ex/v0/ont-second> a owl:Ontology ;
    dcterms:title "Second" ;
    owl:versionInfo "0.1.0" .
"""
    )
    (module_dir / "b.ttl").write_text(second, encoding="utf-8")
    with pytest.raises(InitError):
        run(module_dir, repo_owner="owner")


def test_misnamed_shapes_file_is_classified_by_content_not_filename(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    (module_dir / "ex-constraints.ttl").write_text(SHAPES_TTL, encoding="utf-8")

    kinds = {c.path.name: c.kind for c in discover.discover_all(module_dir)}
    assert kinds["ex-constraints.ttl"] is discover.ContentKind.SHAPES

    run(module_dir, repo_owner="owner")
    assert (module_dir / "spec" / "ex.shacl.ttl").exists()
    assert "sh:NodeShape" not in (module_dir / "spec" / "ex.ttl").read_text(encoding="utf-8")


# re-running, and --clean


def test_rerun_is_noop_without_force(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    run(module_dir, repo_owner="owner")
    env_before = (module_dir / ".env").read_text(encoding="utf-8")

    report = run(module_dir, repo_owner="owner")
    assert report.get("noop")
    assert env_before == (module_dir / ".env").read_text(encoding="utf-8")


def test_clean_removes_generated_files_only(module_dir: Path):
    (module_dir / "keep-me.txt").write_text("hand-written", encoding="utf-8")
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    run(module_dir, repo_owner="owner")
    assert (module_dir / ".env").exists()

    run(module_dir, do_clean=True)
    assert not (module_dir / ".env").exists()
    assert not (module_dir / "spec" / "ex.ttl").exists()
    assert (module_dir / "keep-me.txt").exists()
    assert (module_dir / "ex.ttl").exists(), "the discovered source .ttl is not init's to delete"


def test_clean_on_an_uninitialised_folder_is_a_no_op(module_dir: Path):
    assert run(module_dir, do_clean=True)["cleaned"] == []


def test_a_folder_with_no_ttl_derives_nothing(module_dir: Path):
    report = run(module_dir, repo_owner="owner")
    assert "env" not in report
    assert (module_dir / ".rdl-tools-manifest.json").exists()


# prompts


def test_declining_the_plan_writes_nothing(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    answers = iter(["y", "n"])  # confirm versions, decline the plan
    with pytest.raises(InitError):
        run_init(
            module_dir,
            assume_yes=False,
            skip_install=True,
            repo_owner="owner",
            prompt=lambda _: next(answers),
            out=lambda *a: None,
        )
    assert not (module_dir / ".env").exists()


def test_declining_the_versions_writes_nothing(module_dir: Path):
    (module_dir / "ex.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    with pytest.raises(InitError):
        run_init(
            module_dir,
            assume_yes=False,
            skip_install=True,
            repo_owner="owner",
            prompt=lambda _: "n",
            out=lambda *a: None,
        )
    assert not (module_dir / ".env").exists()


# the CLI surface


def test_a_prompt_with_no_stdin_is_explained_not_a_traceback(module_dir: Path, capsys, monkeypatch):
    def no_stdin(_: str) -> str:
        raise EOFError

    (module_dir / "a.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    monkeypatch.setattr("builtins.input", no_stdin)
    assert main(["init", "--module-dir", str(module_dir), "--skip-install"]) == 2
    err = capsys.readouterr().err
    assert "stdin is closed" in err
    assert "--yes" in err


def test_the_cli_reports_an_init_error_as_exit_1(module_dir: Path, capsys):
    (module_dir / "a.ttl").write_text(ontology_ttl("0.1.0"), encoding="utf-8")
    (module_dir / "b.ttl").write_text(
        PREFIXES + '\n<https://w3id.org/testauth/ex/v0/ont-second> a owl:Ontology ;\n    owl:versionInfo "1" .\n',
        encoding="utf-8",
    )
    assert main(["init", "--module-dir", str(module_dir), "--yes", "--skip-install"]) == 1
    assert "rdl-tools init:" in capsys.readouterr().err


# envwrite


def test_escape_env_value_quotes_hash_and_newlines():
    assert envwrite.escape_env_value("plain") == "plain"
    assert envwrite.escape_env_value("has # hash") == '"has # hash"'
    assert envwrite.escape_env_value("line1\nline2") == '"line1\\nline2"'
    assert envwrite.escape_env_value('has "quotes"') == '"has \\"quotes\\""'


def test_w3id_authority_default_only_for_w3id_namespace():
    assert envwrite.w3id_authority_default("https://w3id.org/apollo-protocol/irm/v0/ont/") == "apollo-protocol"
    assert envwrite.w3id_authority_default("https://example.org/sample/top/v1/ont/") is None


def test_write_env_refuses_to_overwrite_without_force(tmp_path: Path):
    values = envwrite.build_env(
        module_namespace="https://w3id.org/a/b/v0/ont/", slug="b", repo_owner="a", w3id_authority="a"
    )
    envwrite.write_env(tmp_path, values)
    with pytest.raises(FileExistsError):
        envwrite.write_env(tmp_path, values)
    envwrite.write_env(tmp_path, values, force=True)


def test_optional_keys_are_written_only_when_given():
    without = envwrite.build_env(
        module_namespace="https://w3id.org/a/b/v0/ont/", slug="b", repo_owner="a", w3id_authority="a"
    )
    assert "PAGES_ORIGIN" not in without

    rendered = envwrite.render_env(
        envwrite.build_env(
            module_namespace="https://w3id.org/a/b/v0/ont/",
            slug="b",
            repo_owner="a",
            w3id_authority="a",
            pages_origin="https://a.github.io",
            website_base_url="/b/",
        )
    )
    assert "PAGES_ORIGIN=https://a.github.io" in rendered
    assert "WEBSITE_BASE_URL=/b/" in rendered


# discover


def test_non_semver_labels_are_normalised_or_refused():
    assert discover.normalize_semver("0.2.0 (RC2)")[0] == "0.2.0"
    assert discover.normalize_semver("0.2.0 (RC2)")[1] is not None
    assert discover.normalize_semver("1.2.3") == ("1.2.3", None)
    assert discover.normalize_semver("draft")[0] is None


def _candidate(text: str, name: str = "ex.ttl") -> discover.Candidate:
    graph = Graph()
    graph.parse(data=text, format="turtle")
    return discover.Candidate(path=Path(name), graph=graph, kind=discover.ContentKind.ONTOLOGY, source="root")


@pytest.mark.parametrize(
    ("text", "name", "expected"),
    [
        (
            PREFIXES + "\n<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;\n"
            "    owl:versionIRI <https://w3id.org/testauth/ex/v1.2.3/ont> .\n",
            "ex.ttl",
            ("1.2.3", "versionIRI"),
        ),
        (PREFIXES + "\nex:Thing a owl:Class .\n", "ex-9.9.9.ttl", ("9.9.9", "filename")),
        (
            PREFIXES + '\n<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology ;\n    dcterms:modified "2.3.4" .\n',
            "ex.ttl",
            ("2.3.4", "modified"),
        ),
    ],
)
def test_version_resolution_priority(text: str, name: str, expected: tuple[str, str]):
    candidate = _candidate(text, name)
    discover.resolve_version(candidate)
    assert (candidate.version, candidate.version_source) == expected


def test_an_unresolvable_version_records_the_problem():
    candidate = _candidate(PREFIXES + "\n<https://w3id.org/testauth/ex/v0/ont> a owl:Ontology .\n")
    discover.resolve_version(candidate)
    assert candidate.version is None
    assert candidate.version_problem is not None
