"""Unit tests for the site-data generator.

The fixture is fixtures/sample-ont, a small four-dimensionalist top-level ontology in the older
rdfs:Class / rdf:Property style. These check its cross-references, cardinality chips and symmetric
flags, and that the emitted MDX is byte-stable across reruns.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH, SKOS

from rdl_tools.cli import main
from rdl_tools.colour import accent_ramp, srgb_to_oklch
from rdl_tools.commands.render_site_data import (
    ModuleData,
    collect_releases,
    diff_bullets,
    escape_mdx_heading,
    parse_changelog,
    reference_mdx_text,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-ont"

SAMPLE_CLASSES = [
    "Extent",
    "FourPlaceTuple",
    "IntermittentTimespan",
    "RegularSpacetimeExtent",
    "SelfDisconnectedState",
    "Set",
    "SetOfExtents",
    "SpacetimeExtent",
    "State",
    "TemporallyIntermittentState",
    "Thing",
    "Timespan",
    "Tuple",
    "WorldboundExtent",
]
SAMPLE_PROPERTIES = [
    "after",
    "connected",
    "couple",
    "disconnected",
    "groundingRelation",
    "isAFinishOf",
    "isAStartOf",
    "isImproperPartOf",
    "isPartOf",
    "isTemporalPartOf",
    "partWhole",
    "powertype",
    "relationship",
    "relationshipBetweenStates",
    "relationshipBetweenUniverseMates",
    "subSuperRelation",
]

TOP = "https://example.org/sample/top/v0/ont/"


def render(module_dir: Path, *args: str) -> int:
    return main(["render-site-data", "--module-dir", str(module_dir), *args])


def term(local: str) -> URIRef:
    return URIRef(TOP + local)


@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    module = ModuleData(FIXTURE, "0.5.7")
    releases = collect_releases(module, "0.5.7")
    notes = next(r["notes"] for r in releases if r["id"] == "0.5.7")
    return module.version_payload("0.5.7", module.release_date(), True, notes)


@pytest.fixture(scope="module")
def classes(payload: dict[str, Any]) -> dict[str, Any]:
    return {c["id"]: c for c in payload["classes"]}


@pytest.fixture(scope="module")
def properties(payload: dict[str, Any]) -> dict[str, Any]:
    return {p["id"]: p for p in payload["properties"]}


@pytest.fixture
def module() -> ModuleData:
    """A fresh ModuleData, for the tests that mutate its shapes graph or its config."""
    return ModuleData(FIXTURE, "0.5.7")


@pytest.fixture
def module_copy(tmp_path: Path) -> Path:
    module_dir = tmp_path / "sample-ont"
    shutil.copytree(FIXTURE, module_dir)
    return module_dir


# the term set


def test_term_rail_lists_every_term_in_the_fixture(payload: dict[str, Any]):
    assert [c["id"] for c in payload["classes"]] == SAMPLE_CLASSES
    assert [p["id"] for p in payload["properties"]] == SAMPLE_PROPERTIES
    assert payload["counts"] == {"classes": 14, "properties": 16}


def test_foreign_subjects_are_referenced_but_never_listed(classes, properties):
    # The fixture places rdf:type and the two RDFS sub-super properties under the grounding
    # relations, so they surface in Used By without becoming terms of this module.
    for foreign in ("type", "subClassOf", "subPropertyOf"):
        assert foreign not in properties
    assert "Resource" not in classes
    assert "type" in [r["id"] for r in properties["groundingRelation"]["usedBy"]]


def test_skos_definition_wins_over_the_rdfs_comment_fallback(classes):
    assert classes["Extent"]["definitionSource"] == "skos:definition"
    assert classes["Thing"]["definitionSource"] == "rdfs:comment"


def test_local_name_is_the_default_label(classes, properties):
    # rdfs:label on this term is "Four Place Tuple"; TERM_LABEL_SOURCE=localName wins.
    assert classes["FourPlaceTuple"]["label"] == "FourPlaceTuple"
    assert properties["isTemporalPartOf"]["label"] == "isTemporalPartOf"


def test_rdfs_label_source_switches_the_label_but_not_the_anchor(module: ModuleData):
    module.term_label_source = "rdfsLabel"
    record = module.class_record(term("FourPlaceTuple"))
    assert record["label"] == "Four Place Tuple"
    assert record["id"] == "FourPlaceTuple"


# cross-references


def test_extent_refers_to_set_of_extents_via_powertype(classes):
    refers = classes["Extent"]["refersTo"]
    assert [r["id"] for r in refers] == ["SetOfExtents"]
    assert refers[0]["via"] == "sample_top:powertype"
    # powertype is a term of this module, so the reference is an in-page anchor.
    assert not refers[0]["external"]
    assert refers[0]["href"] == "#SetOfExtents"


def test_subclasses_are_not_repeated_in_used_by(classes):
    extent = classes["Extent"]
    assert [r["id"] for r in extent["subClasses"]] == ["SpacetimeExtent", "WorldboundExtent"]
    assert [r["id"] for r in extent["usedBy"]] == ["connected", "disconnected", "partWhole"]


def test_thing_is_used_by_the_couple_relation_only(classes):
    thing = classes["Thing"]
    assert [r["id"] for r in thing["subClasses"]] == ["Extent", "Set", "Tuple"]
    assert [r["id"] for r in thing["usedBy"]] == ["couple"]


def test_state_used_by_lists_the_properties_bound_to_it(classes):
    assert [r["id"] for r in classes["State"]["usedBy"]] == ["isPartOf", "relationshipBetweenStates"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("couple", ["connected", "disconnected", "relationship"]),
        ("isPartOf", ["isImproperPartOf", "isTemporalPartOf"]),
        ("isTemporalPartOf", ["isAFinishOf", "isAStartOf"]),
    ],
)
def test_reverse_sub_property_lookup_feeds_used_by(properties, name: str, expected: list[str]):
    assert [r["id"] for r in properties[name]["usedBy"]] == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("IntermittentTimespan", ["TemporallyIntermittentState", "Timespan"]),
        ("State", ["RegularSpacetimeExtent", "WorldboundExtent"]),
    ],
)
def test_multiple_inheritance_is_kept(classes, name: str, expected: list[str]):
    assert [r["id"] for r in classes[name]["superClasses"]] == expected


def test_external_sub_property_of_resolves_absolutely(properties):
    # sample_top:powertype rdfs:subPropertyOf rdf:type.
    powertype = properties["powertype"]
    assert [r["id"] for r in powertype["subPropertyOf"]] == ["type"]
    assert powertype["subPropertyOf"][0]["external"]
    assert powertype["subPropertyOf"][0]["href"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def test_muted_policy_drops_external_hrefs(module: ModuleData):
    module.external_link_policy = "muted"
    record = module.property_record(term("powertype"))
    assert record["subPropertyOf"][0]["href"] is None
    assert record["subPropertyOf"][0]["external"]


# SHACL


def test_extent_constraint_rows(classes):
    rows = classes["Extent"]["constraints"]
    assert [(r["path"], r["range"]["id"], r["cardinality"]) for r in rows] == [
        ("connected", "Extent", "0..*"),
        ("disconnected", "Extent", "0..*"),
    ]
    # A bare-IRI path stays a linkable ref, and an ordinary shape adds no severity or message.
    assert rows[0]["property"]["id"] == "connected"
    assert rows[0]["severity"] is None
    assert rows[0]["message"] is None


def test_an_inverse_path_shape_renders_a_row_but_no_forward_chip(payload, classes, properties):
    # The one shape targeting IntermittentTimespan through [ sh:inversePath isPartOf ]
    # renders as one row whose path is `^isPartOf`, carrying its own severity and message.
    rows = classes["IntermittentTimespan"]["constraints"]
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == "^isPartOf"
    assert row["property"] is None  # not a bare IRI, so nothing to link
    assert row["range"]["id"] == "TemporallyIntermittentState"
    assert row["severity"] == "Warning"
    assert "TemporallyIntermittentState" in row["message"]
    # The shape declares no counts, so it claims no cardinality.
    assert row["cardinality"] is None
    # And an inverse path constrains the subject, not the forward property.
    assert properties["isPartOf"]["cardinality"] == "0..1"


def test_path_expressions_render_in_sparql_notation(module: ModuleData):
    a, b = term("isPartOf"), term("connected")

    sequence = BNode()
    Collection(module.shapes, sequence, [a, b])
    assert module.path_text(sequence) == "isPartOf / connected"

    alternative_list = BNode()
    Collection(module.shapes, alternative_list, [a, b])
    alternative = BNode()
    module.shapes.add((alternative, SH.alternativePath, alternative_list))
    assert module.path_text(alternative) == "isPartOf | connected"

    one_or_more = BNode()
    module.shapes.add((one_or_more, SH.oneOrMorePath, a))
    assert module.path_text(one_or_more) == "isPartOf+"

    # An alternative inside a modifier is parenthesised, or `a | b+` would reassociate.
    nested = BNode()
    module.shapes.add((nested, SH.zeroOrMorePath, alternative))
    assert module.path_text(nested) == "(isPartOf | connected)*"


def test_a_malformed_path_stops_recursing(module: ModuleData):
    # A path that names itself: without the depth guard this never terminates.
    looping = BNode()
    module.shapes.add((looping, SH.inversePath, looping))
    assert module.path_text(looping).endswith("…")
    assert module.path_text(None) == "…"


def test_a_shape_declaring_no_counts_claims_no_cardinality(module: ModuleData):
    after = term("after")
    silent = BNode()
    module.shapes.add((silent, SH.path, after))
    module.shapes.add((silent, SH["class"], after))
    assert module.property_cardinality(after) is None
    assert module.conflicts == []


def test_state_constraint_row(classes):
    rows = classes["State"]["constraints"]
    assert [(r["property"]["id"], r["range"]["id"], r["cardinality"]) for r in rows] == [("isPartOf", "State", "0..1")]


@pytest.mark.parametrize(("name", "expected"), [("connected", "0..*"), ("isPartOf", "0..1"), ("after", None)])
def test_property_cardinality_chips(properties, name: str, expected: str | None):
    assert properties[name]["cardinality"] == expected


@pytest.mark.parametrize(("name", "expected"), [("connected", True), ("disconnected", True), ("couple", False)])
def test_symmetric_flags(properties, name: str, expected: bool):
    assert properties[name]["symmetric"] is expected


def test_conflicting_cardinalities_omit_the_chip_and_are_reported(module: ModuleData):
    connected = term("connected")
    rogue = BNode()
    module.shapes.add((rogue, SH.path, connected))
    module.shapes.add((rogue, SH.maxCount, Literal(1)))
    assert module.property_cardinality(connected) is None
    assert len(module.conflicts) == 1
    assert "conflicting SHACL cardinalities" in module.conflicts[0]


# metadata


def test_ontology_iri_comes_from_the_ttl_and_the_pin_from_config(payload):
    ontology = payload["ontology"]
    assert ontology["iri"] == "https://example.org/sample/top/v0/ont"
    assert ontology["pinIri"] == "https://w3id.org/sample-org/sample-ont/v0.5.7/ont"
    assert ontology["majorIri"] == "https://w3id.org/sample-org/sample-ont/v0/ont"


def test_license_label_strips_the_html_suffix(payload):
    assert payload["ontology"]["license"] == {"label": "MIT", "href": "https://spdx.org/licenses/MIT.html"}


def test_release_date_follows_release_date_source(payload):
    assert payload["date"] == "2026-08-23"
    assert payload["ontology"]["created"] == "2025-09-30"


def test_namespace_table_is_declaration_order_with_the_module_prefix_last(payload):
    prefixes = [ns["prefix"] for ns in payload["namespaces"]]
    assert prefixes[-1] == "sample_top"
    assert prefixes[:8] == ["rdf", "rdfs", "owl", "xsd", "skos", "sh", "dcterms", "vann"]
    assert "brick" not in prefixes  # rdflib injects these; the file text does not


def test_downloads_are_empty_until_the_pin_is_actually_generated(payload):
    # website/static/v0.5.7/ont/ doesn't exist in the fixture — DOWNLOAD_FORMATS names what a
    # module wants to offer, not what exists yet.
    assert payload["downloads"] == []


def test_downloads_use_a_site_relative_href_and_skip_ungenerated_formats(module_copy: Path):
    pin_dir = module_copy / "website" / "static" / "v0.5.7" / "ont"
    pin_dir.mkdir(parents=True)
    (pin_dir / "ont.ttl").write_text("", encoding="utf-8")
    (pin_dir / "ont.nt").write_text("", encoding="utf-8")

    assert ModuleData(module_copy, "0.5.7").downloads("0.5.7") == [
        {"label": "TTL", "href": "/sample-ont/v0.5.7/ont/ont.ttl"},
        {"label": "N-Triples", "href": "/sample-ont/v0.5.7/ont/ont.nt"},
    ]


def test_a_generated_ledger_adds_a_download_button(module_copy: Path):
    pin_dir = module_copy / "website" / "static" / "v0.5.7" / "ont"
    pin_dir.mkdir(parents=True)
    (pin_dir / "ont.ttl").write_text("", encoding="utf-8")
    (pin_dir / "ledger.ttl").write_text("", encoding="utf-8")

    downloads = ModuleData(module_copy, "0.5.7").downloads("0.5.7")
    assert downloads[-1] == {"label": "Ledger", "href": "/sample-ont/v0.5.7/ont/ledger.ttl"}


# the reference MDX


def test_emitted_mdx_is_byte_stable(module: ModuleData):
    assert reference_mdx_text(module, "0.5.7") == reference_mdx_text(ModuleData(FIXTURE, "0.5.7"), "0.5.7")


def test_headings_carry_case_preserving_anchors(module: ModuleData):
    mdx = reference_mdx_text(module, "0.5.7")
    assert "### Extent {#Extent}" in mdx
    assert "### isTemporalPartOf {#isTemporalPartOf}" in mdx
    assert '<TermBody id="FourPlaceTuple" />' in mdx
    assert "toc_max_heading_level: 3" in mdx


def test_term_order_in_the_page_matches_the_rail(module: ModuleData):
    mdx = reference_mdx_text(module, "0.5.7")
    positions = [mdx.index(f"{{#{name}}}") for name in SAMPLE_CLASSES + SAMPLE_PROPERTIES]
    assert positions == sorted(positions)


def test_markdown_specials_in_a_label_are_escaped():
    assert escape_mdx_heading("a*b_c[d]") == r"a\*b\_c\[d\]"


def test_front_matter_survives_a_multiline_description(module: ModuleData):
    # A triple-quoted dcterms:description must not reach the YAML front matter as raw newlines:
    # that fails the Docusaurus parse before the page ever renders.
    module.title = 'A "quoted": title'
    module.description = (
        "  First paragraph: with a colon,\n  wrapped over lines.\n\nSecond paragraph, which the meta tag drops.\n"
    )
    front_matter = reference_mdx_text(module, "0.5.7").split("---")[1]

    assert len([line for line in front_matter.strip().splitlines() if line]) == 5
    assert 'title: "A \\"quoted\\": title v0.5.7"' in front_matter
    assert 'description: "First paragraph: with a colon, wrapped over lines."' in front_matter
    assert "Second paragraph" not in front_matter


def test_a_module_with_no_description_omits_the_meta_line(module: ModuleData):
    module.description = ""
    assert "description:" not in reference_mdx_text(module, "0.5.7").split("---")[1]


def test_front_matter_parses_as_yaml(module: ModuleData):
    parsed_yaml = pytest.importorskip("yaml", reason="PyYAML is in the dev extra")
    module.description = "Line one: a colon\n#not a comment\n\ntail"
    parsed = parsed_yaml.safe_load(reference_mdx_text(module, "0.5.7").split("---")[1])
    assert parsed["slug"] == "/"
    assert parsed["description"] == "Line one: a colon #not a comment"


# changelogs


def test_front_matter_date_and_bullets_are_parsed(tmp_path: Path):
    path = tmp_path / "v0.5.7.md"
    path.write_text(
        "---\ndate: 2026-08-23\n---\n\n<!-- a comment -->\n\n- First note.\n- Second note.\n",
        encoding="utf-8",
    )
    assert parse_changelog(path) == ("2026-08-23", ["First note.", "Second note."])


def test_a_changelog_without_front_matter_still_yields_bullets(tmp_path: Path):
    path = tmp_path / "v0.5.7.md"
    path.write_text("* Star bullets count too.\n\nProse does not.\n", encoding="utf-8")
    assert parse_changelog(path) == (None, ["Star bullets count too."])


def without_subject(graph: Graph, marker: str) -> Graph:
    trimmed = Graph()
    for triple in graph:
        if marker not in str(triple[0]):
            trimmed.add(triple)
    return trimmed


def test_diff_reports_added_terms_and_moved_ranges(module: ModuleData):
    previous = without_subject(module.merged, "IntermittentTimespan")
    bullets = diff_bullets(previous, module.merged, module)
    assert "Added class `IntermittentTimespan`." in bullets
    assert "`IntermittentTimespan` gained superclass `Timespan`." in bullets


def test_a_removed_term_does_not_also_get_a_redundant_lost_relationship_bullet(module: ModuleData):
    current = without_subject(module.merged, "IntermittentTimespan")
    bullets = diff_bullets(module.merged, current, module)
    assert "Removed class `IntermittentTimespan`." in bullets
    assert not [b for b in bullets if b.startswith("`IntermittentTimespan` lost")], (
        "a removed term's own relationship losses are implied, not separate news"
    )


def test_a_reworded_definition_is_reported(module: ModuleData):
    current = Graph()
    for triple in module.merged:
        current.add(triple)
    current.set((term("Extent"), SKOS.definition, Literal("Something else entirely.")))

    assert "Reworded the definition of `Extent`." in diff_bullets(module.merged, current, module)


def test_a_removed_shacl_constraint_is_reported(module: ModuleData):
    current = Graph()
    for triple in module.merged:
        current.add(triple)
    for shape in list(current.subjects(SH.targetClass, None)):
        for property_shape in list(current.objects(shape, SH.property)):
            current.remove((shape, SH.property, property_shape))

    bullets = diff_bullets(module.merged, current, module)
    assert [b for b in bullets if b.startswith("Removed the SHACL constraint on")]


# the drift gate and the generated tree


def test_a_module_namespace_disagreeing_with_the_rdf_fails_the_build(module_copy: Path):
    env_path = module_copy / ".env"
    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "MODULE_NAMESPACE=https://example.org/sample/top/v0/ont/",
            "MODULE_NAMESPACE=https://example.org/somewhere-else/v0/ont/",
        ),
        encoding="utf-8",
    )
    assert render(module_copy, "--check") == 1


def test_accent_colour_emits_a_generated_stylesheet_and_removing_it_deletes_it(module_copy: Path):
    accent_path = module_copy / "website" / "src" / "css" / "accent.generated.css"
    env_path = module_copy / ".env"

    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace("ACCENT_COLOR=", "ACCENT_COLOR=#5980a6"), encoding="utf-8"
    )
    assert render(module_copy, "--version", "0.5.7") == 0
    assert "--rdl-accent-600" in accent_path.read_text(encoding="utf-8")

    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace("ACCENT_COLOR=#5980a6", "ACCENT_COLOR="), encoding="utf-8"
    )
    assert render(module_copy, "--version", "0.5.7") == 0
    assert not accent_path.exists()


def test_check_writes_nothing_but_still_writes_the_coverage_report(module_copy: Path, tmp_path: Path):
    report = tmp_path / "ci-report" / "annotation-coverage.json"
    assert render(module_copy, "--check", "--coverage-report", str(report)) == 0
    assert not (module_copy / "website" / "docs" / "reference.mdx").exists()
    assert report.exists()


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_no_generated_file_carries_a_windows_line_ending(module_copy: Path):
    # The determinism guarantee is cross-platform, and the two-run test cannot see this: it
    # compares runs on one OS.
    assert render(module_copy, "--version", "0.5.7", "--draft-changelog") == 0
    written = [
        *(module_copy / "website" / "src" / "generated").rglob("*"),
        module_copy / "website" / "docs" / "reference.mdx",
        module_copy / "changelog" / "v0.5.7.md",
    ]
    for path in (p for p in written if p.is_file()):
        assert b"\r\n" not in path.read_bytes(), path


def test_generated_output_is_byte_identical_across_two_runs(tmp_path: Path):
    trees = []
    for name in ("first", "second"):
        module_dir = tmp_path / name / "sample-ont"
        shutil.copytree(FIXTURE, module_dir)
        assert render(module_dir, "--version", "0.5.7") == 0
        trees.append(tree_bytes(module_dir / "website" / "src" / "generated"))
    assert trees[0] == trees[1]


# the doc-version snapshot guard
#
# website/docs/reference.mdx is a single working copy, so rendering a new version must refuse
# while the previous one has no `docusaurus docs:version` snapshot in website/versions.json.


@pytest.fixture
def unsnapshotted(module_copy: Path) -> Path:
    generated_dir = module_copy / "website" / "src" / "generated"
    generated_dir.mkdir(parents=True)
    (generated_dir / "0.5.6.json").write_text("{}", encoding="utf-8")
    return module_copy


def test_refuses_to_render_a_new_version_over_an_unsnapshotted_previous_one(unsnapshotted: Path):
    assert render(unsnapshotted, "--version", "0.5.7") == 1
    assert not (unsnapshotted / "website" / "docs" / "reference.mdx").exists()


def test_proceeds_once_the_previous_version_is_snapshotted(unsnapshotted: Path):
    (unsnapshotted / "website" / "versions.json").write_text('["0.5.6"]', encoding="utf-8")
    assert render(unsnapshotted, "--version", "0.5.7") == 0
    assert (unsnapshotted / "website" / "docs" / "reference.mdx").exists()


def test_a_corrupt_versions_json_is_treated_as_no_snapshots(unsnapshotted: Path):
    (unsnapshotted / "website" / "versions.json").write_text("not json", encoding="utf-8")
    assert render(unsnapshotted, "--version", "0.5.7") == 1


def test_reminds_to_cut_this_versions_snapshot_immediately_not_next_time(unsnapshotted: Path, capsys):
    (unsnapshotted / "website" / "versions.json").write_text('["0.5.6"]', encoding="utf-8")
    assert render(unsnapshotted, "--version", "0.5.7") == 0
    out = capsys.readouterr().out
    assert "docusaurus docs:version 0.5.7" in out
    assert "not deferred to the next release" in out


def test_no_reminder_on_the_very_first_release(module_copy: Path, capsys):
    assert render(module_copy, "--version", "0.5.7") == 0
    assert "docusaurus docs:version" not in capsys.readouterr().out


def test_re_rendering_the_same_version_needs_no_prior_snapshot(unsnapshotted: Path):
    assert render(unsnapshotted, "--version", "0.5.6") == 0


# --draft-changelog


def test_a_first_release_draft_is_written_and_never_overwritten(module_copy: Path):
    assert render(module_copy, "--version", "0.5.7", "--draft-changelog") == 0
    draft = module_copy / "changelog" / "v0.5.7.md"
    assert "Initial release of" in draft.read_text(encoding="utf-8")

    draft.write_text("---\ndate: 2026-01-01\n---\n\n- Hand written.\n", encoding="utf-8")
    assert render(module_copy, "--version", "0.5.7", "--draft-changelog") == 0
    assert "Hand written." in draft.read_text(encoding="utf-8")


def test_a_draft_against_a_previous_pin_lists_the_delta(module_copy: Path):
    pin_dir = module_copy / "website" / "static" / "v0.5.6" / "ont"
    pin_dir.mkdir(parents=True)
    previous = without_subject(ModuleData(module_copy, "0.5.7").merged, "IntermittentTimespan")
    previous.serialize(destination=str(pin_dir / "ont.ttl"), format="turtle", encoding="utf-8")
    (module_copy / "website" / "versions.json").write_text('["0.5.6"]', encoding="utf-8")

    assert render(module_copy, "--version", "0.5.7", "--draft-changelog") == 0
    draft = (module_copy / "changelog" / "v0.5.7.md").read_text(encoding="utf-8")
    assert "Added class `IntermittentTimespan`." in draft


# the accent ramp


def test_industry_steel_round_trips_to_the_expected_lightness():
    lightness, chroma, hue = srgb_to_oklch((0x59 / 255, 0x80 / 255, 0xA6 / 255))  # #5980a6
    assert lightness == pytest.approx(0.57, abs=0.03)
    assert chroma > 0.02
    assert 230 < hue < 270


def test_ramp_is_monotonically_darker_and_holds_hue():
    ramp = accent_ramp("#5980a6")
    stops = sorted(ramp)
    lightnesses = [ramp[stop][0] for stop in stops]
    assert lightnesses == sorted(lightnesses, reverse=True)
    assert len({ramp[stop][2] for stop in stops}) == 1


def test_a_bad_accent_is_rejected():
    with pytest.raises(ValueError, match="6-digit hex"):
        accent_ramp("not-a-colour")
