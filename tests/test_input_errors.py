"""Input mistakes: each is refused with exit 2 and one message that names the problem and its fix.

A broken Turtle file, a spec/ file name with no handler, and a command run from a folder that is
not a module. Every path in a message is relative to the module folder.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PureWindowsPath

import pytest

from rdl_tools.cli import main
from rdl_tools.commands import fetch_fonts
from rdl_tools.spec import shown

# The issue's reproduction. rdflib reports the missing dot at line 13, the EOF after the last line.
BROKEN = """# spec/min.ttl (last statement has no closing dot)
@prefix ex: <https://example.org/min/v0/ont/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vann: <http://purl.org/vocab/vann/> .

<https://example.org/min/v0/ont> a owl:Ontology ;
    rdfs:label "Min" ;
    vann:preferredNamespaceUri "https://example.org/min/v0/ont/" .

ex:Thing a owl:Class .
ex:Broken a owl:Class
"""
VALID = BROKEN + " .\n"
SECOND_ONTOLOGY = (
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<https://example.org/other/v0/ont> a owl:Ontology .\n"
)
SYNTAX_ERROR = "line 13: Bad syntax (EOF found after object)"
ENV = "W3ID_AUTHORITY=sample-org\nMODULE_SLUG=min\n"
NOT_A_MODULE_FIX = "Run from the module root or pass --module-dir"


def make_module(root: Path, files: dict[str, str]) -> Path:
    """A module checkout under `root`: the skeleton, .env, and each `files` entry by relative path."""
    module_dir = root / "min"
    (module_dir / "website").mkdir(parents=True)
    (module_dir / "spec").mkdir()
    (module_dir / "requirements.txt").write_text("rdl-tools==0.1.0\n", encoding="utf-8")
    (module_dir / ".env").write_text(ENV, encoding="utf-8")
    for relative, text in files.items():
        path = module_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return module_dir


def exit_code(argv: Sequence[str]) -> int:
    """The command's exit status, whether `run` returns it or a shared gate raises SystemExit."""
    try:
        return main(list(argv))
    except SystemExit as exc:
        return int(exc.code or 0)


def tree(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


# a Turtle syntax error

# (id, files, argv after the command name, where --module-dir is filled in, broken file)
PARSE_CASES = [
    ("validate", {"spec/min.ttl": BROKEN}, ["validate", "--no-imports"], "spec/min.ttl"),
    (
        "validate-shapes",
        {"spec/min.ttl": VALID, "spec/min.shacl.ttl": BROKEN},
        ["validate", "--no-imports"],
        "spec/min.shacl.ttl",
    ),
    ("format", {"spec/min.ttl": BROKEN}, ["format", "--check"], "spec/min.ttl"),
    ("render-docs", {"spec/min.ttl": BROKEN}, ["render-docs", "--version", "0.1.0"], "spec/min.ttl"),
    (
        "render-site-data",
        {"spec/min.ttl": BROKEN},
        ["render-site-data", "--version", "0.1.0", "--check"],
        "spec/min.ttl",
    ),
    ("init", {"spec/min.ttl": BROKEN}, ["init", "--yes", "--skip-install"], "spec/min.ttl"),
    (
        "expand-pins",
        {"spec/min.ttl": VALID, "website/static/v0.1.0/ont/ont.ttl": BROKEN},
        ["expand-pins"],
        "website/static/v0.1.0/ont/ont.ttl",
    ),
    (
        "draft-changelog",
        {"spec/min.ttl": VALID, "website/static/v0.1.0/ont/ont.ttl": BROKEN},
        ["render-site-data", "--version", "0.2.0", "--draft-changelog"],
        "website/static/v0.1.0/ont/ont.ttl",
    ),
]


@pytest.mark.parametrize(
    ("files", "argv", "broken"),
    [case[1:] for case in PARSE_CASES],
    ids=[case[0] for case in PARSE_CASES],
)
def test_a_turtle_syntax_error_exits_2_on_one_line_naming_file_and_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, files: dict[str, str], argv: list[str], broken: str
):
    module_dir = make_module(tmp_path, files)
    # validate and format resolve spec/ against the working directory; the others get an
    # absolute --module-dir, so a relative path in the message proves it was made relative.
    monkeypatch.chdir(module_dir)
    if argv[0] not in ("validate", "format"):
        argv = [*argv, "--module-dir", str(module_dir)]
    assert exit_code(argv) == 2
    assert capsys.readouterr().err.splitlines()[-1] == f"{broken}: {SYNTAX_ERROR}"


# paths relative to the module


@pytest.mark.parametrize(
    "argv",
    [
        ["validate", "--no-imports"],
        ["format", "--check"],
        ["render-docs", "--version", "0.1.0"],
        ["render-site-data", "--version", "0.1.0", "--check"],
    ],
    ids=["validate", "format", "render-docs", "render-site-data"],
)
def test_an_unsupported_spec_file_name_is_shown_relative_to_the_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, argv: list[str]
):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID, "spec/min.notes.ttl": VALID})
    monkeypatch.chdir(module_dir)
    if argv[0] not in ("validate", "format"):
        argv = [*argv, "--module-dir", str(module_dir)]
    assert exit_code(argv) == 2
    assert capsys.readouterr().err.startswith("spec/min.notes.ttl is not a supported spec/ file name.")


@pytest.mark.parametrize("command", ["render-docs", "render-site-data"])
def test_an_empty_spec_dir_is_shown_relative_to_the_module(tmp_path: Path, capsys, command: str):
    module_dir = make_module(tmp_path, {})
    assert exit_code([command, "--module-dir", str(module_dir), "--version", "0.1.0"]) == 2
    assert capsys.readouterr().err.splitlines()[-1] == "No ontology .ttl files found in spec"


def test_a_second_ontology_subject_is_shown_relative_to_the_module(tmp_path: Path, capsys):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID, "spec/other.ttl": SECOND_ONTOLOGY})
    assert exit_code(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 2
    assert "in the merged graph from spec/*.ttl:" in capsys.readouterr().err


def test_render_docs_reports_the_pins_it_wrote_relative_to_the_module(tmp_path: Path, capsys):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Wrote website/static/v0.1.0/ont/ and website/static/v0/ont/"


def test_render_docs_reports_an_existing_pin_relative_to_the_module(tmp_path: Path, capsys):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert main(["render-docs", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 1
    assert capsys.readouterr().err.startswith("website/static/v0.1.0 already exists")


def test_expand_pins_reports_the_static_dir_relative_to_the_module(tmp_path: Path, capsys):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    assert main(["expand-pins", "--module-dir", str(module_dir)]) == 0
    assert capsys.readouterr().out.startswith("No pins with a committed ont.ttl under website/static ")


# a folder that is not a module

NOT_A_MODULE_ARGV = {
    "render-docs": ["render-docs", "--version", "0.1.0"],
    "render-site-data": ["render-site-data", "--version", "0.1.0"],
    "expand-pins": ["expand-pins"],
    "fetch-fonts": ["fetch-fonts"],
}


@pytest.mark.parametrize("cwd", ["website", "spec", ".."])
@pytest.mark.parametrize("command", sorted(NOT_A_MODULE_ARGV))
def test_a_folder_that_is_not_a_module_is_refused_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, command: str, cwd: str
):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID, "website/static/v0.1.0/ont/ont.ttl": VALID})

    def no_network(url: str, *, browser: bool = False) -> bytes:
        raise AssertionError(f"fetch-fonts reached the network: {url}")

    monkeypatch.setattr(fetch_fonts, "fetch", no_network)
    monkeypatch.chdir(module_dir / cwd)
    before = tree(tmp_path)
    assert exit_code(NOT_A_MODULE_ARGV[command]) == 2
    err = capsys.readouterr().err
    assert "is not a module folder: no website or requirements.txt." in err
    assert NOT_A_MODULE_FIX in err
    assert tree(tmp_path) == before


@pytest.mark.parametrize("argv", [["validate", "--no-imports"], ["format", "--check"]], ids=["validate", "format"])
def test_a_missing_spec_dir_names_the_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, argv: list[str]):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    monkeypatch.chdir(module_dir / "website")
    assert exit_code(argv) == 2
    assert capsys.readouterr().err == "spec is not a directory. Run from the module root or pass --spec-dir.\n"


def test_a_file_that_is_not_utf8_exits_2_on_one_line_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    module_dir = make_module(tmp_path, {})
    (module_dir / "spec" / "min.ttl").write_bytes(VALID.replace('"Min"', '"M\xefn"').encode("latin-1"))
    monkeypatch.chdir(module_dir)
    assert exit_code(["validate", "--no-imports"]) == 2
    assert capsys.readouterr().err.splitlines()[-1].startswith("spec/min.ttl: not UTF-8")


def test_a_blank_node_ontology_subject_is_shown_relative_to_the_module(tmp_path: Path, capsys):
    ontology = VALID.replace("<https://example.org/min/v0/ont> a owl:Ontology", "[] a owl:Ontology")
    module_dir = make_module(tmp_path, {"spec/min.ttl": ontology})
    assert exit_code(["render-site-data", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 2
    assert capsys.readouterr().err.splitlines()[-1] == "No owl:Ontology subject found in spec/*.ttl"


# `/` in every message, on every OS


@pytest.mark.parametrize(
    ("path", "root", "expected"),
    [
        (r"C:\m\spec\min.ttl", r"C:\m", "spec/min.ttl"),
        (r"spec\min.ttl", ".", "spec/min.ttl"),
        (r"D:\elsewhere\old.ttl", r"C:\m", r"D:\elsewhere\old.ttl"),
    ],
    ids=["inside-absolute", "inside-relative", "outside"],
)
def test_a_windows_path_is_shown_with_forward_slashes_inside_the_root(path: str, root: str, expected: str):
    assert shown(PureWindowsPath(path), PureWindowsPath(root)) == expected  # type: ignore[arg-type]


def test_format_reports_the_files_it_rewrote_with_forward_slashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    monkeypatch.chdir(module_dir)
    assert main(["format", "--check"]) == 1
    assert "spec/min.ttl is not canonically formatted." in capsys.readouterr().err
    assert main(["format"]) == 0
    assert "Reformatted spec/min.ttl" in capsys.readouterr().out


def test_render_site_data_reports_the_files_it_wrote_with_forward_slashes(tmp_path: Path, capsys):
    module_dir = make_module(tmp_path, {"spec/min.ttl": VALID})
    assert main(["render-site-data", "--module-dir", str(module_dir), "--version", "0.1.0"]) == 0
    assert "Wrote website/src/generated/site.json" in capsys.readouterr().out.splitlines()
