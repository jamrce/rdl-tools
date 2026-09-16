"""The spec/ gates: what `rdl-tools validate` and `rdl_tools.spec` refuse to let through.

Each test builds a throwaway spec directory, because every gate is about the *set* of files in
one directory rather than about any single graph.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdl_tools.cli import main
from rdl_tools.commands.fmt import is_published_pin
from rdl_tools.spec import merge_ontology

PREFIXES = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/ex/v0/ont/> .
"""

ONTOLOGY = (
    PREFIXES
    + """
<https://example.org/ex/v0/ont> a owl:Ontology .
ex:Thing a owl:Class .
ex:anInstance a ex:Thing .
"""
)

SECOND_ONTOLOGY = (
    PREFIXES
    + """
<https://example.org/other/v0/ont> a owl:Ontology .
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


@pytest.fixture
def spec_dir(tmp_path: Path):
    """Writes a spec/ directory. `__` in a keyword spells `.`: these gates key off the filename."""

    def write(**files: str) -> Path:
        for name, text in files.items():
            (tmp_path / name.replace("__", ".")).write_text(text, encoding="utf-8")
        return tmp_path

    return write


def test_a_second_owl_ontology_subject_is_refused(spec_dir):
    spec = spec_dir(ex__ttl=ONTOLOGY, other__ttl=SECOND_ONTOLOGY)
    with pytest.raises(SystemExit) as raised:
        merge_ontology(spec)
    assert raised.value.code == 2


def test_a_single_ontology_merges(spec_dir):
    assert len(merge_ontology(spec_dir(ex__ttl=ONTOLOGY))) > 0


def test_no_ontology_subject_at_all_is_refused(spec_dir):
    spec = spec_dir(ex__ttl=PREFIXES + "\nex:Thing a owl:Class .\n")
    with pytest.raises(SystemExit) as raised:
        merge_ontology(spec)
    assert raised.value.code == 2


def test_a_module_with_no_shapes_passes_with_a_notice(spec_dir):
    assert main(["validate", "--spec-dir", str(spec_dir(ex__ttl=ONTOLOGY))]) == 0


def test_shapes_outside_a_shacl_file_are_refused(spec_dir):
    # Merged as ontology source today: published inside the graph, validating nothing.
    assert main(["validate", "--spec-dir", str(spec_dir(ex__ttl=ONTOLOGY + SHAPES))]) == 2


def test_shapes_in_a_shacl_file_are_validated(spec_dir):
    # ex:Thing carries no rdfs:label, so the sh:minCount 1 shape must fail it.
    spec = spec_dir(ex__ttl=ONTOLOGY, ex__shacl__ttl=SHAPES)
    assert main(["validate", "--spec-dir", str(spec)]) == 1


def test_no_imports_validates_the_same_without_dereferencing_anything(spec_dir):
    spec = spec_dir(ex__ttl=ONTOLOGY, ex__shacl__ttl=SHAPES)
    assert main(["validate", "--spec-dir", str(spec), "--no-imports"]) == 1


def test_a_missing_spec_dir_is_an_argument_error_not_a_traceback():
    assert main(["validate", "--spec-dir", "no/such/dir"]) == 2


def test_an_empty_spec_dir_is_refused(tmp_path: Path):
    assert main(["validate", "--spec-dir", str(tmp_path)]) == 2


def test_a_published_pin_is_recognised():
    assert is_published_pin(Path("website/static/v0.1.0/ont/ont.ttl"))
    assert not is_published_pin(Path("spec/replace-me.ttl"))
