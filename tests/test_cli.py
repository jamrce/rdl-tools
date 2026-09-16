"""The CLI surface itself: every subcommand is reachable, self-documenting and dispatchable.

The wheel smoke test in CI runs the same `--help` calls against an installed console script; this
runs them in-process so a broken parser fails fast on every push.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from rdl_tools import __version__
from rdl_tools.cli import COMMANDS, load, main

README = Path(__file__).resolve().parents[1] / "README.md"

EXPECTED_COMMANDS = {
    "init",
    "validate",
    "format",
    "expand-pins",
    "render-docs",
    "render-site-data",
    "fetch-fonts",
}


def test_the_command_set_is_exactly_what_a_module_build_needs():
    assert set(COMMANDS) == EXPECTED_COMMANDS


@pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
def test_every_subcommand_has_help_and_exits_zero(name, capsys):
    with pytest.raises(SystemExit) as raised:
        main([name, "--help"])
    assert raised.value.code == 0
    assert name in capsys.readouterr().out


@pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
def test_every_subcommand_module_implements_the_contract(name):
    assert COMMANDS[name].help
    module = load(name)
    assert callable(module.add_parser)
    assert callable(module.run)


def test_listing_the_commands_imports_none_of_them():
    # The whole point of the registry: `--help` and `--version` must not pay for rdflib.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from rdl_tools import cli; cli.build_parser(); print('rdflib' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_top_level_help_lists_every_command(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for name in EXPECTED_COMMANDS:
        assert name in out


def test_version_flag_reports_the_package_version(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_is_an_argument_error():
    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == 2


def test_an_unknown_command_is_an_argument_error():
    with pytest.raises(SystemExit) as raised:
        main(["nope"])
    assert raised.value.code == 2


def test_the_readme_command_table_matches_the_cli():
    """Row order is the order `--help` prints; each description is that command's registry help."""
    rows = re.findall(r"^\| `([a-z-]+)` \| (.+?) \|$", README.read_text(encoding="utf-8"), re.MULTILINE)
    assert [name for name, _ in rows] == list(COMMANDS), "README table is missing, reordered or out of date"
    for name, described in rows:
        assert described.replace("`", "") == COMMANDS[name].help, name


def test_the_module_entry_point_works():
    # For a user without the console script on PATH: `pip install --target`, a vendored venv.
    result = subprocess.run(
        [sys.executable, "-m", "rdl_tools", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert __version__ in result.stdout
