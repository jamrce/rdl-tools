"""`rdl_tools.spec` (the shared view of spec/ and .env) and `rdl_tools.bootstrap` (local setup).

These two modules are used by every generator, so their edge cases are worth naming individually
rather than reaching only through a command.
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from rdl_tools import bootstrap, spec

# spec


def test_local_name_handles_slash_hash_and_trailing_separators():
    assert spec.local_name("https://example.org/a/b/Thing") == "Thing"
    assert spec.local_name("https://example.org/a#Thing") == "Thing"
    assert spec.local_name("https://example.org/a/b/") == "b"


def test_semver_key_only_matches_a_v_prefixed_triple():
    assert spec.semver_key("v1.2.3") == (1, 2, 3)
    assert spec.semver_key("v0") is None
    assert spec.semver_key("1.2.3") is None


def test_version_key_sorts_non_semver_last():
    assert sorted(["0.10.0", "0.9.0", "1.0.0"], key=spec.version_key) == ["0.9.0", "0.10.0", "1.0.0"]
    assert spec.version_key("draft") == (0, 0, 0)


def test_find_previous_pin_ignores_v0_and_the_version_being_cut(tmp_path: Path):
    static = tmp_path / "static"
    for name in ("v0", "v0.1.0", "v0.2.0", "v0.3.0", "not-a-pin"):
        (static / name).mkdir(parents=True)
    assert spec.find_previous_pin(static, "0.3.0") == static / "v0.2.0"
    # "Previous" means highest-excluding-this-one, not highest-below-this-one. Re-cutting an old
    # version out of order therefore chains owl:priorVersion to a *newer* pin — which is why
    # render-docs refuses to overwrite a pin without --force.
    assert spec.find_previous_pin(static, "0.1.0") == static / "v0.3.0"
    assert spec.find_previous_pin(tmp_path / "absent", "0.1.0") is None


def test_find_previous_pin_returns_none_when_only_the_new_pin_exists(tmp_path: Path):
    static = tmp_path / "static"
    (static / "v0.1.0").mkdir(parents=True)
    assert spec.find_previous_pin(static, "0.1.0") is None


def test_ontology_files_excludes_shapes_and_ledgers(tmp_path: Path):
    for name in ("a.ttl", "a.shacl.ttl", "a.generated.ttl", "notes.md"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert [p.name for p in spec.ontology_files(tmp_path)] == ["a.ttl"]
    assert [p.name for p in spec.shape_files(tmp_path)] == ["a.shacl.ttl"]


def test_declared_prefixes_are_file_order_not_rdflib_order(tmp_path: Path):
    first = tmp_path / "a.ttl"
    first.write_text(
        "@prefix zed: <https://example.org/z/> .\n@prefix alpha: <https://example.org/a/> .\n",
        encoding="utf-8",
    )
    second = tmp_path / "b.ttl"
    second.write_text("@prefix alpha: <https://example.org/other/> .\n", encoding="utf-8")
    # Declaration order wins, first declaration of a prefix wins, and rdflib's own bindings
    # (brick, csvw, …) never appear.
    assert spec.declared_prefixes([first, second]) == [
        ("zed", "https://example.org/z/"),
        ("alpha", "https://example.org/a/"),
    ]


def test_read_env_strips_comments_quotes_and_blank_lines(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "# a comment\n\nA=1\nB=two  # trailing comment\nC=\"quoted\"\nD='single'\nnot a pair\n",
        encoding="utf-8",
    )
    assert spec.read_env(tmp_path) == {"A": "1", "B": "two", "C": "quoted", "D": "single"}


def test_read_env_on_a_folder_without_one_is_empty(tmp_path: Path):
    assert spec.read_env(tmp_path) == {}


def test_generated_output_is_written_with_lf_on_every_platform(tmp_path: Path):
    # Path.write_text would translate these to CRLF on Windows and diff against Linux CI.
    target = tmp_path / "generated.json"
    spec.write_generated(target, "first\nsecond\n")
    assert target.read_bytes() == b"first\nsecond\n"


def test_merge_ontology_on_an_empty_directory_exits_two(tmp_path: Path, capsys):
    with pytest.raises(SystemExit) as raised:
        spec.merge_ontology(tmp_path)
    assert raised.value.code == 2


# skeleton


def test_a_folder_without_a_website_is_refused_with_an_explanation(tmp_path: Path):
    from rdl_tools import skeleton

    missing = skeleton.missing_parts(tmp_path)
    assert "website" in missing and "requirements.txt" in missing
    message = skeleton.explain(tmp_path, missing)
    assert "rdl-module-template" in message
    assert "does not create one" in message


def test_a_module_checkout_is_recognised(tmp_path: Path):
    from rdl_tools import skeleton

    (tmp_path / "website").mkdir()
    (tmp_path / "requirements.txt").write_text("rdl-tools==0.0.0\n", encoding="utf-8")
    assert skeleton.missing_parts(tmp_path) == []


# bootstrap


def test_activate_workflows_renames_once_and_then_stays_put(tmp_path: Path):
    (tmp_path / "github" / "workflows").mkdir(parents=True)
    assert bootstrap.activate_workflows(tmp_path) == tmp_path / ".github"
    assert (tmp_path / ".github" / "workflows").is_dir()
    assert bootstrap.activate_workflows(tmp_path) is None


def test_activate_workflows_is_a_no_op_without_a_github_folder(tmp_path: Path):
    assert bootstrap.activate_workflows(tmp_path) is None


def test_skip_install_leaves_the_environment_alone(tmp_path: Path):
    notes = bootstrap.finish_setup(tmp_path, skip_install=True)
    assert any("skip-install" in note for note in notes)
    assert not (tmp_path / ".venv").exists()


def bin_dir_with(tmp_path: Path, *names: str) -> Path:
    website = tmp_path / "website"
    target = website / "node_modules" / ".bin"
    target.mkdir(parents=True)
    for name in names:
        (target / name).write_text("", encoding="utf-8")
    return website


def test_a_foreign_platform_node_modules_is_detected(tmp_path: Path):
    on_windows = platform.system() == "Windows"
    # A POSIX tree carries no .cmd; a Windows tree carries nothing but extensionless shims.
    website = bin_dir_with(tmp_path, "docusaurus" if on_windows else "docusaurus.cmd")
    message = bootstrap.node_modules_platform_mismatch(website)
    assert message is not None
    assert ("POSIX-installed" if on_windows else "Windows-installed") in message


def test_a_matching_node_modules_reports_no_mismatch(tmp_path: Path):
    # npm on Windows writes the extensionless shim beside the .cmd and .ps1, so a healthy Windows
    # tree holds both. Reading an extensionless entry as POSIX would wipe it on every init.
    names = ("docusaurus", "docusaurus.cmd", "docusaurus.ps1") if platform.system() == "Windows" else ("docusaurus",)
    assert bootstrap.node_modules_platform_mismatch(bin_dir_with(tmp_path, *names)) is None


def test_no_node_modules_at_all_reports_no_mismatch(tmp_path: Path):
    website = tmp_path / "website"
    website.mkdir()
    assert bootstrap.node_modules_platform_mismatch(website) is None
    (website / "node_modules").mkdir()
    assert bootstrap.node_modules_platform_mismatch(website) is None
